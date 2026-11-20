"""Build a static copy of the dashboard in ./site for GitHub Pages. No server needed."""

from __future__ import annotations

import html
import json
import os
import shutil
from pathlib import Path

import app

BASE_DIR = Path(__file__).resolve().parent
SITE_DIR = BASE_DIR / "site"
DAY_RANGES = (1, 3, 7)  # the Today / 3 days / Week buttons in the UI


def main() -> None:
    shutil.rmtree(SITE_DIR, ignore_errors=True)
    (SITE_DIR / "data").mkdir(parents=True)

    for days in DAY_RANGES:
        payload = json.dumps(app.build_payload(days), default=str, ensure_ascii=False)
        (SITE_DIR / "data" / f"news-{days}.json").write_text(payload, encoding="utf-8")

    shutil.copytree(BASE_DIR / "static", SITE_DIR / "static")

    page = (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")
    if "<head>" not in page:
        raise SystemExit("templates/index.html has no <head> tag to put the static-build marker in.")
    repo = html.escape(os.getenv("GITHUB_REPOSITORY", ""))
    page = page.replace("<head>", f'<head>\n  <meta name="static-build" content="{repo}">', 1)
    (SITE_DIR / "index.html").write_text(page, encoding="utf-8")

    (SITE_DIR / ".nojekyll").touch()
    print(f"Built {SITE_DIR}")


if __name__ == "__main__":
    main()
