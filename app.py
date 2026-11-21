"""AI Daily: a local dashboard of AI news that refreshes itself every morning.

Run:  python app.py      then open http://127.0.0.1:5050
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timedelta

from flask import Flask, abort, jsonify, render_template, request

import news

REFRESH_HOUR = int(os.getenv("NEWS_REFRESH_HOUR", "7"))
REFRESH_MINUTE = int(os.getenv("NEWS_REFRESH_MINUTE", "0"))
PORT = int(os.getenv("NEWS_PORT", "5050"))
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
TOP_SOURCES = {"TechCrunch", "The Verge", "Wired", "MIT Tech Review", "Ars Technica", "Reuters",
               "Bloomberg", "The New York Times", "Financial Times", "CNBC", "VentureBeat"}

app = Flask(__name__)


# --------------------------------------------------------------------------- schedule

def _todays_slot(now: datetime) -> datetime:
    return now.replace(hour=REFRESH_HOUR, minute=REFRESH_MINUTE, second=0, microsecond=0)


def next_refresh(now: datetime | None = None) -> datetime:
    now = now or datetime.now().astimezone()
    slot = _todays_slot(now)
    return slot if now < slot else slot + timedelta(days=1)


def needs_refresh() -> bool:
    """True if we have not refreshed since the most recent morning slot."""
    last = news.get_meta("last_updated")
    if not last:
        return True
    now = datetime.now().astimezone()
    slot = _todays_slot(now)
    latest_slot = slot if now >= slot else slot - timedelta(days=1)
    return datetime.fromisoformat(last).astimezone() < latest_slot


def scheduler_loop() -> None:
    # Re-check every few minutes instead of one long sleep, so a laptop that was asleep
    # at 07:00 still refreshes soon after it wakes up.
    while True:
        if needs_refresh():
            print(f"[{datetime.now():%H:%M}] refreshing news…", flush=True)
            result = news.refresh()
            print(f"[{datetime.now():%H:%M}] done: {result.get('new', 0)} new, "
                  f"errors: {list(result.get('errors', {}))}", flush=True)
        time.sleep(300)


# --------------------------------------------------------------------------- ranking

_WORD_RE = re.compile(r"[a-z0-9]{3,}")


def _words(title: str) -> set[str]:
    return {w for w in _WORD_RE.findall(title.lower()) if w not in news.STOPWORDS}


def add_coverage(articles: list[dict]) -> None:
    """Count how many other outlets ran a similar headline; a rough 'big story' signal."""
    word_sets = [_words(a["title"]) for a in articles]
    for i, article in enumerate(articles):
        mine, sources = word_sets[i], {article["source"]}
        if len(mine) >= 3:
            for j, other in enumerate(word_sets):
                if i != j and len(other) >= 3 and len(mine & other) / len(mine | other) >= 0.3:
                    sources.add(articles[j]["source"])
        article["coverage"] = len(sources)


def pick_featured(articles: list[dict], count: int = 3) -> list[int]:
    def score(a: dict) -> float:
        age_hours = (datetime.now().astimezone() - datetime.fromisoformat(a["published"])).total_seconds() / 3600
        return (a["coverage"] * 3 + (4 if a["image"] else 0) + (2 if a["source"] in TOP_SOURCES else 0)
                + (1 if a["summary"] else 0) - age_hours / 6)

    ranked = sorted((a for a in articles if a["category"] != "Thailand"), key=score, reverse=True)
    featured, seen_titles = [], []
    for a in ranked:
        words = _words(a["title"])
        if any(len(words & s) >= 2 or len(words & s) / max(len(words | s), 1) >= 0.3 for s in seen_titles):
            continue  # don't feature the same story twice
        featured.append(a["id"])
        seen_titles.append(words)
        if len(featured) == count:
            break
    return featured


# --------------------------------------------------------------------------- payload

MAX_BRIEF_ITEMS = 5
MAX_MODEL_CHARS = 60
# Max length per brief item field. None means keep as is: the url must match articles.json exactly.
BRIEF_ITEM_LIMITS = {"title_th": 200, "summary_th": 600, "title_en": 200, "summary_en": 600,
                     "url": None, "source": 100}


def clean_summary(raw: object, known_urls: set[str]) -> dict | None:
    """Keep only brief items that are well formed and point at one of the day's articles.

    The brief is written by a routine that reads untrusted news text, so treat it as untrusted too.
    """
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        return None
    generated, model = raw.get("generated"), raw.get("model")
    if not isinstance(generated, str) or not isinstance(model, str):
        return None

    items, seen_urls = [], set()
    for item in raw["items"]:
        if not isinstance(item, dict):
            continue
        if not all(isinstance(item.get(field), str) and item[field].strip() for field in BRIEF_ITEM_LIMITS):
            continue
        url = item["url"]
        if not url.startswith(("https://", "http://")) or url not in known_urls or url in seen_urls:
            continue
        seen_urls.add(url)
        items.append({field: item[field] if limit is None else item[field][:limit]
                      for field, limit in BRIEF_ITEM_LIMITS.items()})
        if len(items) == MAX_BRIEF_ITEMS:
            break

    if not items:
        return None
    return {"generated": generated, "model": model[:MAX_MODEL_CHARS], "items": items}


def load_summary() -> dict | None:
    try:
        brief_input = json.loads(news.ARTICLES_PATH.read_text(encoding="utf-8"))
        known_urls = {a["url"] for a in brief_input["articles"] if isinstance(a, dict) and isinstance(a.get("url"), str)}
        known_urls |= {u for u in brief_input.get("brief_urls", []) if isinstance(u, str)}
        raw = json.loads(news.SUMMARY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return clean_summary(raw, known_urls)


def build_payload(days: int) -> dict:
    articles = news.get_articles(days)
    add_coverage(articles)
    return {
        "articles": articles,
        "featured": pick_featured(articles),
        "trending": news.trending_keywords(articles),
        "summary": load_summary(),
        "last_updated": news.get_meta("last_updated"),
        "next_update": next_refresh().isoformat(),
        "refreshing": news.is_refreshing(),
        "sources_configured": len(news.FEEDS),
    }


# --------------------------------------------------------------------------- routes

@app.before_request
def reject_foreign_hosts():
    # A DNS-rebinding page reaches 127.0.0.1 under its own hostname, so only our names are served.
    if request.host not in ALLOWED_HOSTS:
        abort(403)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/news")
def api_news():
    days = max(1, min(int(request.args.get("days", 1)), news.KEEP_DAYS))
    return jsonify(build_payload(days))


@app.post("/api/refresh")
def api_refresh():
    # A JSON body forces a CORS preflight, which a cross-site form or fetch can't pass.
    if not request.is_json:
        abort(415)
    return jsonify(news.refresh())


if __name__ == "__main__":
    threading.Thread(target=scheduler_loop, daemon=True).start()
    print(f"AI Daily running at http://127.0.0.1:{PORT}  (auto-refresh daily at "
          f"{REFRESH_HOUR:02d}:{REFRESH_MINUTE:02d})")
    app.run(host="127.0.0.1", port=PORT, debug=False)
