# AI Daily

A local Python dashboard of the day's AI news. It pulls headlines from about a dozen public RSS feeds, sorts them into topics, and updates every morning.

## Run it

Double-click **`start_dashboard.bat`**. The first run sets up a virtual environment. The dashboard then opens at <http://127.0.0.1:5050>.

To run it by hand:

```bash
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

## Morning updates

There are two ways it stays fresh, and you can use both:

1. **While `app.py` is running**, it refreshes at 07:00 each day. If the computer was asleep at 07:00, it refreshes as soon as it wakes up. An open browser tab picks up new stories automatically.
2. **Windows Task Scheduler** fetches news at 07:00 even when the dashboard isn't open, so stories are ready when you start it:

   ```powershell
   .\install_morning_task.ps1                 # daily fetch at 07:00
   .\install_morning_task.ps1 -Time 06:30     # different time
   .\install_morning_task.ps1 -StartAtLogon   # also start the dashboard when you sign in
   .\install_morning_task.ps1 -Uninstall      # remove the tasks
   ```

   Each run adds a line to `data/update.log`.

To change the in-app refresh time, set environment variables before starting: `NEWS_REFRESH_HOUR=6`, `NEWS_REFRESH_MINUTE=30`, `NEWS_PORT=5050`.

## Run it on GitHub (every morning, no PC needed)

The workflow in `.github/workflows/daily.yml` runs on GitHub's servers every day at 07:00 Bangkok time. Each run:

1. Fetches the latest news into `data/news.db`. The database is kept between runs in the Actions cache, so the Week view fills up over time.
2. Asks Claude Sonnet 5.5 for a short morning brief of the top stories, in Thai with an English version under each item (`summarize.py`).
3. Builds a static copy of the dashboard in `site/` (`build_static.py`).
4. Publishes it to GitHub Pages at `https://<user>.github.io/ai-news-dashboard/`.
5. Commits a one-line `last-run.txt`. GitHub turns off scheduled workflows in repositories with no recent commits, and this keeps it running.

To set it up:

1. Push this folder to a GitHub repository named `ai-news-dashboard`.
2. In the repository, open **Settings > Pages** and set **Source** to **GitHub Actions**.
3. Add your Claude API key: **Settings > Secrets and variables > Actions > New repository secret**. Name it `ANTHROPIC_API_KEY` and paste the key as the value.

You can skip step 3 at first. Without the key, the site still updates every morning. It just has no morning brief until you add the key.

The API key comes from <https://platform.claude.com>. API usage is billed separately from a Claude chat subscription (Pro or Max), so you need to add credit there even if you already pay for Claude.

**Cost (an estimate).** The brief is one Claude Sonnet 5.5 call per day, roughly 10K input and 3K output tokens. At $2 per million input tokens and $10 per million output tokens, that is about $0.05 a day. Fetching feeds and hosting on GitHub Pages are free for public repositories.

**Timing.** GitHub can start scheduled runs late, sometimes by 30 minutes or more when its servers are busy.

**Run it by hand.** Open the **Actions** tab, pick **Daily AI news**, and click **Run workflow**. On the published site, the refresh button links to this page.

## Features

- **Top stories**: three featured cards, ranked by how many outlets ran the story, recency, and whether there's an image
- **Topic filters**: Models & Research, Business, Policy & Society, Products, Health & Science, Chips & Hardware, Thailand
- **Search**: press `/` to jump to the search box. Click a trending term or outlet to search for it
- **Today / 3 days / Week** time range
- **"N outlets" badge** on stories that many publishers are covering
- **Save for later** and read tracking, kept in your browser
- **Dark mode** that follows your system setting and remembers your choice
- Works on phone-sized screens too

## Files

| File | What it does |
|---|---|
| `news.py` | Feed list, fetching, topic tagging, SQLite storage (`data/news.db`, keeps 30 days) |
| `app.py` | Flask server, JSON API, morning scheduler, top-story ranking |
| `update_news.py` | Fetches once and exits (used by Task Scheduler) |
| `summarize.py` | Asks Claude for the Thai + English morning brief and writes `data/summary.json` (skipped without `ANTHROPIC_API_KEY`) |
| `build_static.py` | Builds the static GitHub Pages copy of the dashboard in `site/` |
| `.github/workflows/daily.yml` | Daily GitHub Actions run: fetch, brief, build, publish |
| `templates/`, `static/` | Dashboard UI (HTML, CSS, vanilla JS) |

## Adding or changing sources

Edit `FEEDS` at the top of `news.py`. Any RSS or Atom URL works. Optional keys:

- `"category"` puts everything from that feed under one topic.
- `"limit"` caps how many items the feed keeps per refresh (default 40).

Topic keywords are in `CATEGORIES` in the same file.

A feed that fails is skipped and the rest still update. For example, VentureBeat sometimes rate-limits.
