"""Write the day's top stories to brief/articles.json for the Claude Code routine.

The routine reads this file each morning, writes brief/summary.json, and pushes it.
"""

from __future__ import annotations

import json
from datetime import datetime

import app
import news

MAX_ARTICLES = 40
FIELDS = ("title", "source", "summary", "url", "coverage", "published")


def pick_articles(articles: list[dict]) -> list[dict]:
    ranked = sorted(articles, key=lambda a: (a["coverage"], a["published"]), reverse=True)
    return [{field: a[field] for field in FIELDS} for a in ranked[:MAX_ARTICLES]]


def published_brief_urls() -> list[str]:
    """Links of the brief on the site that were on the previous allow-list.

    The site only shows brief links found in this file, so without them a new
    input file would hide the current brief until the routine writes the next one.
    """
    try:
        old = json.loads(news.ARTICLES_PATH.read_text(encoding="utf-8"))
        allowed = {a["url"] for a in old["articles"]} | set(old.get("brief_urls", []))
        items = json.loads(news.SUMMARY_PATH.read_text(encoding="utf-8"))["items"]
        return [i["url"] for i in items if i.get("url") in allowed]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []


def main() -> None:
    articles = news.get_articles(1)
    app.add_coverage(articles)
    brief_input = {
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "articles": pick_articles(articles),
        "brief_urls": published_brief_urls(),
    }
    news.ARTICLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    news.ARTICLES_PATH.write_text(json.dumps(brief_input, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(brief_input['articles'])} articles to {news.ARTICLES_PATH}")


if __name__ == "__main__":
    main()
