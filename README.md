# AI Daily

A Python dashboard of the day's AI news. It pulls headlines from about a dozen public RSS feeds, sorts them into topics, and updates every morning.

**Open the live dashboard: https://korawitjung.github.io/ai-news-dashboard/**

It works from any device and updates itself each morning, with a Thai and English brief written by Claude.

## Run it on your own computer

Double-click **`start_dashboard.bat`**. The first run sets up a virtual environment. The dashboard then opens at <http://127.0.0.1:5050>.

That address points at your own computer, not at GitHub. It only works on the computer running `start_dashboard.bat`, while that window stays open.

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

## How the morning update works (no PC needed)

Two services work together. A Claude Code routine runs in the cloud on your Claude plan, so there is no API key and no separate bill. A GitHub Actions workflow (`.github/workflows/daily.yml`) fetches the news and publishes the site to GitHub Pages.

The routine is the clock. GitHub's own schedules started about four hours late in testing, while the routine fires within a few minutes of its time. A push to the repository starts the workflow within seconds, so the routine starts each step with a push.

Each morning, in Bangkok time:

| Time | Who | What happens |
|---|---|---|
| 06:40 | Claude routine | Clones the repository. Stops here if today's brief is already published. Otherwise writes the request time to `brief/request.json` and pushes it. |
| 06:41 | GitHub workflow | The push starts it. It fetches every feed into `data/news.db`, writes the top 40 stories of the last 24 hours to `brief/articles.json` and commits that file, then rebuilds and publishes the site. The news on the site is now fresh. |
| 06:42 | Claude routine | Has been checking every 20 seconds. Once `brief/articles.json` is newer than its request, it picks the five biggest AI stories, writes them in Thai with English under each to `brief/summary.json`, checks the file, and pushes it. |
| 06:45 | GitHub workflow | The push starts it again. It fetches the news once more and publishes the site with the new brief. |

The news and the brief are normally live by about 06:50. The routine can start a few minutes late, so allow until 07:00.

**Midday refresh.** The workflow also has a GitHub schedule at 11:13. GitHub often starts it later. It only adds newer stories, and the morning brief stays on the site.

**The brief stays until the next one.** Every run writes a new `brief/articles.json`. It keeps the links of the brief on the site in `brief_urls`, so a later run never hides the brief.

**Run it by hand.**

- *News only:* open the **Actions** tab, pick **Daily AI news**, and click **Run workflow**. On the published site, the refresh button links to this page.
- *News and brief:* open <https://claude.ai>, go to **Code**, then **Routines**, open **AI Daily morning brief (TH/EN)**, and click **Run now**. If today's brief is already published, the routine does nothing.

**Set it up from scratch.**

1. Push this folder to a GitHub repository named `ai-news-dashboard`.
2. In the repository, open **Settings > Pages** and set **Source** to **GitHub Actions**.
3. Install the Claude GitHub App on this repository only, so the routine can push.
4. Create the routine at <https://claude.ai/code/routines> with the settings and prompt in `routine-prompt.md`.

## When something goes wrong

Check the site first, then follow the row that matches.

| What you see on the site | What it means | What to do |
|---|---|---|
| Fresh news and today's brief | Everything worked. | Nothing. |
| The brief is from yesterday, the news is old | The routine didn't run, or its push of `brief/request.json` failed. | Open the routine's latest run under **Code > Routines**. Its last message says what went wrong. Click **Run now** to try again. |
| The brief is from yesterday, the news is new | The news fetch worked but the routine stopped before writing the brief. The routine waits 15 minutes for news, then gives up. | Read the routine's last message. Then click **Run now**. |
| Nothing changed at all | The workflow failed, or GitHub Pages didn't publish. | Open the **Actions** tab. A red run shows which step failed. Click **Re-run jobs**. |
| A red run with "A push may change only…" | A push changed a file the routine may not touch, so the workflow refused to build. | Look at that commit. If you made it yourself, that's expected: start a run with **Run workflow**. If you didn't, check who made it. |

The routine also sends a notification to your phone when it gives up, if notifications are on for your Claude account.

## Security

News text comes from public RSS feeds, so anyone can write it. The project treats it as untrusted.

- **The site escapes news text.** Titles, summaries and sources are shown as plain text, never run as HTML.
- **The brief is checked before it is shown.** The routine reads news text, so a news item could try to trick it. `app.py` keeps only brief items whose link is one of the day's articles in `brief/articles.json`. It drops items with missing fields, cuts long text, and shows at most five.
- **The workflow only builds pushes from the routine's two files.** If a push changes any file other than `brief/request.json` and `brief/summary.json`, or either file is over its size limit (1 KB and 64 KB), the run stops before anything is built or published.
- **That check has a limit.** A push that edits the workflow file itself runs its own edited workflow, so the check can't stop it. GitHub permissions are the real limit. Install the Claude GitHub App on this repository only. Protect `main` with a ruleset. Turn on two-factor authentication for your GitHub account.
- **Versions are pinned.** `requirements.txt` lists exact versions of every Python package. Each GitHub Action is pinned to a fixed commit.
- **The local app only answers on 127.0.0.1.** It rejects requests that use any other host name, and the refresh button needs a JSON request. Another website open in your browser can't use it.

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
| `brief/` | `request.json` (the routine's request for fresh news), `articles.json` (the routine's input) and `summary.json` (the Thai + English brief the routine writes, shown above Top stories) |
| `build_static.py` | Builds the static GitHub Pages copy of the dashboard in `site/` |
| `.github/workflows/daily.yml` | GitHub Actions run: fetch, export brief input, build, publish. Starts when the routine pushes `brief/request.json` or `brief/summary.json`, and at midday |
| `templates/`, `static/` | Dashboard UI (HTML, CSS, vanilla JS) |

## Adding or changing sources

Edit `FEEDS` at the top of `news.py`. Any RSS or Atom URL works. Optional keys:

- `"category"` puts everything from that feed under one topic.
- `"limit"` caps how many items the feed keeps per refresh (default 40).

Topic keywords are in `CATEGORIES` in the same file.

A feed that fails is skipped and the rest still update. For example, VentureBeat sometimes rate-limits.


>## Disclaimer
>- **The news belongs to its publishers.** Headlines and short summaries come from the publishers' public RSS feeds, and every story links to the original article. This project is not affiliated with or endorsed by any of them. Read the full story on the publisher's site.
>- **The morning brief is written by AI.** Claude writes it automatically from the day's headlines, and nobody checks it before it is published. It can get facts wrong, miss context or mistranslate. Check the original article before you rely on it or share it.
>- **This is not professional advice.** Nothing on the dashboard is financial, investment, legal or medical advice.
>- **No guarantee.** Feeds can fail, stories can be missing or late, and the site can go down. The software is provided as is, under the license below.
>
>**ข้อจำกัดความรับผิดชอบ.** ข่าวทั้งหมดเป็นของสำนักข่าวต้นทาง แดชบอร์ดนี้แสดงเพียงพาดหัวและสรุปสั้นจาก RSS สาธารณะ พร้อมลิงก์ไปยังข่าวต้นฉบับ และไม่มีส่วนเกี่ยวข้องกับสำนักข่าวใด สรุปข่าวเช้าเขียนโดย AI (Claude) โดยอัตโนมัติและไม่มีคนตรวจก่อนเผยแพร่ จึงอาจมีข้อผิดพลาดหรือแปลคลาดเคลื่อน โปรดตรวจสอบกับข่าวต้นฉบับก่อนนำไปใช้หรือแชร์ เนื้อหาทั้งหมดไม่ใช่คำแนะนำด้านการเงิน การลงทุน กฎหมาย หรือการแพทย์

## License

The code is released under the [MIT License](LICENSE). The license covers this project's code only. News headlines, summaries and images remain the property of their publishers.
