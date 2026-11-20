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
2. Writes the top 40 stories of the last 24 hours to `brief/articles.json` (`export_brief_input.py`) and commits it. GitHub turns off scheduled workflows in repositories with no recent commits, and this daily commit keeps it running.
3. Builds a static copy of the dashboard in `site/` (`build_static.py`).
4. Publishes it to GitHub Pages at `https://<user>.github.io/ai-news-dashboard/`.

To set it up:

1. Push this folder to a GitHub repository named `ai-news-dashboard`.
2. In the repository, open **Settings > Pages** and set **Source** to **GitHub Actions**.

**Timing.** GitHub can start scheduled runs late, sometimes by 30 minutes or more when its servers are busy.

**Run it by hand.** Open the **Actions** tab, pick **Daily AI news**, and click **Run workflow**. On the published site, the refresh button links to this page.

## Morning brief from Claude (no API key)

The Thai and English morning brief comes from a Claude Code routine. It runs in the cloud on your Claude plan, so there is no API key and no separate bill.

Each morning at about 07:30 Bangkok time, the routine:

1. Clones this repository and reads `brief/articles.json`.
2. Picks the five biggest AI stories and writes them in Thai, with English under each one, to `brief/summary.json`.
3. Commits and pushes that file.

The push starts the workflow again, which rebuilds the site with the new brief.

If the 07:00 run is late and `brief/articles.json` is not from today, the routine skips that day. It does not summarize old news. The site keeps the last brief until the next one.

**See or run the routine.** Open <https://claude.ai>, go to **Code**, then **Routines**. You can see past runs there, and run it now by hand.

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
| `export_brief_input.py` | Writes the day's top 40 stories to `brief/articles.json` for the Claude Code routine |
| `brief/` | `articles.json` (the routine's input) and `summary.json` (the Thai + English brief the routine writes, shown above Top stories) |
| `build_static.py` | Builds the static GitHub Pages copy of the dashboard in `site/` |
| `.github/workflows/daily.yml` | Daily GitHub Actions run: fetch, export brief input, build, publish. Runs again when the routine pushes the brief |
| `templates/`, `static/` | Dashboard UI (HTML, CSS, vanilla JS) |

## Adding or changing sources

Edit `FEEDS` at the top of `news.py`. Any RSS or Atom URL works. Optional keys:

- `"category"` puts everything from that feed under one topic.
- `"limit"` caps how many items the feed keeps per refresh (default 40).

Topic keywords are in `CATEGORIES` in the same file.

A feed that fails is skipped and the rest still update. For example, VentureBeat sometimes rate-limits.
