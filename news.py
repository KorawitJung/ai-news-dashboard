"""Fetch AI news from RSS feeds, tag it by topic, and store it in SQLite."""

from __future__ import annotations

import html
import re
import sqlite3
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

import feedparser

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "news.db"
SUMMARY_PATH = BASE_DIR / "brief" / "summary.json"
ARTICLES_PATH = BASE_DIR / "brief" / "articles.json"
KEEP_DAYS = 30
USER_AGENT = "Mozilla/5.0 (AI-News-Dashboard; personal RSS reader)"
MAX_FEED_BYTES = 5 * 1024 * 1024

# Feeds need no API keys. Add or remove freely.
# A feed can set "category" to override keyword tagging for everything it returns,
# and "limit" to cap how many of its newest items are kept per refresh (default 40).
FEEDS = [
    {"name": "Google News", "limit": 50, "url": "https://news.google.com/rss/search?q=%22artificial+intelligence%22+OR+%22generative+AI%22+when:2d&hl=en-US&gl=US&ceid=US:en"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "VentureBeat", "url": "https://venturebeat.com/category/ai/feed/"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
    {"name": "Ars Technica", "url": "https://arstechnica.com/ai/feed/"},
    {"name": "Wired", "url": "https://www.wired.com/feed/tag/ai/latest/rss"},
    {"name": "Hacker News", "url": "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT&points=150"},
    {"name": "OpenAI", "url": "https://openai.com/news/rss.xml"},
    {"name": "Google AI", "url": "https://blog.google/technology/ai/rss/"},
    {"name": "Google News TH", "category": "Thailand", "limit": 25,
     "url": "https://news.google.com/rss/search?q=AI+OR+%E0%B8%9B%E0%B8%B1%E0%B8%8D%E0%B8%8D%E0%B8%B2%E0%B8%9B%E0%B8%A3%E0%B8%B0%E0%B8%94%E0%B8%B4%E0%B8%A9%E0%B8%90%E0%B9%8C+when:2d&hl=th&gl=TH&ceid=TH:th"},
]

# Keyword rules for topic tagging. The category with the most hits wins.
CATEGORIES = {
    "Models & Research": r"\b(models?|llms?|gpt-?[\w.]*|gemini|claude|llama|mistral|deepseek|qwen|grok|research\w*|scientists?|study|studies|paper|benchmarks?|reasoning|open[- ](source|weights?)|training|datasets?|arxiv|agi|neural|machine learning)\b",
    "Business": r"\b(funding|raises?|raised|valuation|acqui\w+|ipo|invest\w*|revenue|startups?|deals?|billions?|millions?|trillions?|layoffs?|jobs|earnings|stocks?|shares?|markets?|economy|economic|companies|ceo|profit\w*|imf|bubble|correction)\b",
    "Policy & Society": r"\b(regulat\w+|laws?|legal|polic(y|ies)|safety|safeguard\w*|copyright|lawsuits?|sues?|sued|bans?|congress|senate|lawmakers?|eu|ai act|governments?|governance|ethic\w*|moral\w*|deepfakes?|privacy|courts?|white house|bills?|guardrails?|risks?|security|misinformation|schools?|students?|education|teachers?|college|cyber\w*|fbi|trump|china|apec)\b",
    "Products": r"\b(launch\w*|apps?|features?|releases?|released|rolls? out|updates?|chatbots?|assistants?|available|introduc\w+|unveil\w*|announc\w+|copilot|agents?|agentic|tools?|chatgpt|search|browser|users|developers?|lenses)\b",
    "Health & Science": r"\b(health\w*|medic\w*|clinic\w*|doctors?|hospitals?|patients?|fda|cms|drugs?|cancer|diagnos\w*|biolog\w*|biotech|genom\w*|protein|climate|agricultur\w*|scien\w*|physics|echocardiograph\w*|imaging)\b",
    "Chips & Hardware": r"\b(nvidia|chips?|gpus?|data ?cent(er|re)s?|semiconductors?|tpus?|amd|intel|tsmc|compute|robot\w*|hardware|devices?|smartphones?|glasses|energy|power|drones?|uav)\b",
}
_CATEGORY_RE = {name: re.compile(pattern, re.I) for name, pattern in CATEGORIES.items()}

STOPWORDS = set("""
a an the and or but if of to in on at for from by with about as into over after before under
is are was were be been being it its this that these those he she they we you i his her their our
new how why what when who will can could would should may might more most just not no than then
says said say year years day week today now first one two get gets got make makes made via amid
ai artificial intelligence generative using use uses used here there all up out off also your my
""".split())

_refresh_lock = Lock()


# --------------------------------------------------------------------------- storage

def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title_key TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            source TEXT,
            feed TEXT,
            category TEXT,
            image TEXT,
            published TEXT NOT NULL,
            fetched TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_published ON articles(published);
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        """
    )
    return conn


def get_meta(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))


# --------------------------------------------------------------------------- parsing helpers

_TAG_RE = re.compile(r"<[^>]+>")
_IMG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)", re.I)


def _clean_text(raw: str, limit: int = 280) -> str:
    text = html.unescape(_TAG_RE.sub(" ", raw or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text


def _title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9฀-๿]+", "", title.lower())[:90]


def _published(entry) -> datetime:
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(field)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _image(entry) -> str | None:
    for field in ("media_content", "media_thumbnail"):
        for media in entry.get(field) or []:
            if media.get("url"):
                return media["url"]
    for link in entry.get("links") or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image"):
            return link.get("href")
    for block in [entry.get("summary", "")] + [c.get("value", "") for c in entry.get("content") or []]:
        match = _IMG_RE.search(block or "")
        if match:
            return html.unescape(match.group(1))
    return None


def categorize(text: str) -> str:
    scores = {name: len(rx.findall(text)) for name, rx in _CATEGORY_RE.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "General"


def _download(url: str, attempts: int = 2) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read(MAX_FEED_BYTES + 1)
            if len(body) > MAX_FEED_BYTES:
                raise ValueError("feed larger than 5 MB")
            return body
        except urllib.error.HTTPError as exc:
            # Rate limited or briefly down: wait and try once more.
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
            time.sleep(8)
    raise RuntimeError("unreachable")


def _parse_feed(feed: dict) -> list[dict]:
    parsed = feedparser.parse(_download(feed["url"]))

    items = []
    for entry in parsed.entries[: feed.get("limit", 40)]:
        title = _clean_text(entry.get("title", ""), limit=300)
        url = entry.get("link")
        if not title or not url:
            continue

        source = feed["name"]
        # Google News puts the real publisher in <source> and appends " - Publisher" to titles.
        if "news.google.com" in feed["url"]:
            publisher = (entry.get("source") or {}).get("title")
            if publisher:
                source = publisher
                if title.endswith(f" - {publisher}"):
                    title = title[: -len(publisher) - 3].strip()
            summary = ""  # Google News summaries just repeat the title
        else:
            summary = _clean_text(entry.get("summary", ""))

        items.append({
            "url": url,
            "title": title,
            "title_key": _title_key(title),
            "summary": summary,
            "source": source,
            "feed": feed["name"],
            "category": feed.get("category") or categorize(f"{title} {summary}"),
            "image": _image(entry),
            "published": _published(entry).isoformat(),
        })
    return items


# --------------------------------------------------------------------------- refresh

def refresh() -> dict:
    """Pull every feed, store new articles, prune old ones. Safe to call from many threads."""
    if not _refresh_lock.acquire(blocking=False):
        return {"status": "busy"}
    try:
        results, errors = [], {}

        def fetch(feed):
            try:
                return feed["name"], _parse_feed(feed), None
            except Exception as exc:  # one broken feed must not stop the others
                return feed["name"], [], str(exc)

        with ThreadPoolExecutor(max_workers=8) as pool:
            for name, items, error in pool.map(fetch, FEEDS):
                results.extend(items)
                if error:
                    errors[name] = error

        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
        with connect() as conn:
            before = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            conn.executemany(
                """INSERT OR IGNORE INTO articles
                   (url, title_key, title, summary, source, feed, category, image, published, fetched)
                   VALUES (:url, :title_key, :title, :summary, :source, :feed, :category, :image, :published, :fetched)""",
                [{**item, "fetched": now.isoformat()} for item in results if item["published"] >= cutoff],
            )
            conn.execute("DELETE FROM articles WHERE published < ?", (cutoff,))
            after = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            _set_meta(conn, "last_updated", now.isoformat())

        return {"status": "ok", "fetched": len(results), "new": max(after - before, 0),
                "total": after, "errors": errors, "updated": now.isoformat()}
    finally:
        _refresh_lock.release()


def is_refreshing() -> bool:
    return _refresh_lock.locked()


# --------------------------------------------------------------------------- queries

def get_articles(days: int = 1) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM articles WHERE published >= ? ORDER BY published DESC LIMIT 600", (since,)
        ).fetchall()
    return [dict(row) for row in rows]


def trending_keywords(articles: list[dict], top: int = 14) -> list[tuple[str, int]]:
    """Most-mentioned names and terms in headlines (capitalised words and acronyms)."""
    counts: Counter[str] = Counter()
    for article in articles:
        seen = set()
        for word in re.findall(r"\b[A-Z][A-Za-z0-9\-\.]{1,}\b", article["title"]):
            word = word.rstrip(".")
            if word.lower() in STOPWORDS or len(word) < 3 or word in seen:
                continue
            seen.add(word)
            counts[word] += 1
    return [(w, c) for w, c in counts.most_common(top) if c > 1]


if __name__ == "__main__":
    print(refresh())
