"""Fetch the latest AI news once and exit. Windows Task Scheduler runs this every morning."""

from datetime import datetime

import news

if __name__ == "__main__":
    result = news.refresh()
    line = (f"{datetime.now():%Y-%m-%d %H:%M}  status={result.get('status')}  "
            f"new={result.get('new', 0)}  total={result.get('total', 0)}  "
            f"failed={','.join(result.get('errors', {})) or '-'}")
    log = news.DB_PATH.parent / "update.log"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line)
