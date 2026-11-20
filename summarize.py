"""Ask Claude for a short Thai and English morning brief of the day's top AI stories.

Writes data/summary.json, which the dashboard shows above Top stories.
Needs ANTHROPIC_API_KEY; without it this prints a notice and exits cleanly.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

import anthropic

import app
import news

MODEL = "claude-sonnet-5-5"
MAX_ARTICLES = 40
MAX_ITEMS = 5

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title_th": {"type": "string"},
                    "summary_th": {"type": "string"},
                    "title_en": {"type": "string"},
                    "summary_en": {"type": "string"},
                    "url": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["title_th", "summary_th", "title_en", "summary_en", "url", "source"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You write a short morning brief of AI news for a reader in Thailand, in Thai with an English version.

You will get a list of news articles from the last 24 hours. Pick the 5 most significant AI stories.

For each story:
- title_th: a short headline in natural Thai.
- summary_th: one or two sentences in natural Thai on what happened and why it matters.
- title_en: the same headline in concise English.
- summary_en: the same summary in concise English, one or two sentences.
- url: the URL of the article you are summarizing, copied exactly from the list.
- source: the outlet name of that article, as given in the list.

Rules:
- Write the Thai the way a Thai journalist would, not as a word-for-word translation. Keep product and company names in English.
- The English version says the same thing as the Thai, not more.
- No hype or marketing language. State facts plainly.
- If several articles cover the same story, merge them into one item and use the URL of the most informative one.
- Prefer stories covered by more outlets.
- Use only the articles and URLs given. Do not add facts that are not in them."""


def pick_articles(articles: list[dict]) -> list[dict]:
    ranked = sorted(articles, key=lambda a: (a["coverage"], a["published"]), reverse=True)
    return ranked[:MAX_ARTICLES]


def format_articles(articles: list[dict]) -> str:
    blocks = []
    for i, a in enumerate(articles, 1):
        lines = [f"[{i}] {a['title']}",
                 f"Source: {a['source']} | Outlets covering this story: {a['coverage']}",
                 f"URL: {a['url']}"]
        if a["summary"]:
            lines.append(f"Summary: {a['summary']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def keep_known_items(items: list[dict], known_urls: set[str]) -> list[dict]:
    """Drop items citing a URL we did not send, and repeats; the model must only cite given stories."""
    kept, seen = [], set()
    for item in items:
        if item["url"] in known_urls and item["url"] not in seen:
            kept.append(item)
            seen.add(item["url"])
    return kept[:MAX_ITEMS]


def ask_claude(articles_text: str) -> list[dict]:
    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": articles_text}],
    )
    if response.stop_reason == "refusal":
        raise SystemExit("Claude declined to write the brief.")
    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        raise SystemExit(f"Claude returned no text (stop_reason={response.stop_reason}).")
    return json.loads(text)["items"]


def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; skipping the Claude morning brief.")
        return

    articles = news.get_articles(1)
    if not articles:
        print("No articles from the last 24 hours; skipping the Claude morning brief.")
        return
    app.add_coverage(articles)
    chosen = pick_articles(articles)

    items = keep_known_items(ask_claude(format_articles(chosen)), {a["url"] for a in chosen})
    if not items:
        sys.exit("Claude's brief cited none of the given articles; not writing summary.json.")

    summary = {
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": MODEL,
        "items": items,
    }
    news.SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(items)} brief items to {news.SUMMARY_PATH}")


if __name__ == "__main__":
    main()
