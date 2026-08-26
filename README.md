# amc-ticket-bot

Watches AMC Lincoln Square 13 (NYC) for IMAX 70mm ticket availability for
"Odyssey" and pings a Telegram chat the moment matching tickets go on sale,
including a live seat-availability count. Runs on a schedule via GitHub
Actions — no server to maintain.

## How it works

AMC's developer API (`developers.amctheatres.com`) gates seating and
showtime-listing access behind a contractual approval process with no
self-service option — there's no vendor key that gets you this data. So
this project reads AMC's public website directly instead, via a headless
browser (Playwright/Chromium, needed to clear Cloudflare's bot check):

1. `amc_monitor/showtime_scraper.py` scrapes the movie's showtimes-listing
   page for the configured theatre/format across a rolling window of
   upcoming days.
2. Diffs the found showtime ids against `state.json` (ids already notified
   about) and, for any new non-sold-out showtime, scrapes its
   seat-selection page (`amc_monitor/seat_scraper.py`) for a live
   available/total seat count.
3. Sends a Telegram message with the showtime, time, and seat count.
4. The GitHub Actions workflow commits the updated `state.json` back to the
   branch so re-runs don't send duplicate alerts.

This is inherently fragile: it depends on AMC's current page markup and on
Chromium continuing to clear Cloudflare's challenge, neither of which is
guaranteed to keep working. If AMC changes their site, `showtime_scraper.py`
and `seat_scraper.py` are where to look — see the module docstrings for the
exact markup each one currently expects.

## One-time setup

### 1. Telegram bot

You've already created the bot via @BotFather. To get your numeric chat id:

1. Send any message to your bot in Telegram.
2. Run:
   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"
   ```
3. Read `message.chat.id` out of the response.

### 2. Add GitHub Actions secrets

In the repo's Settings → Secrets and variables → Actions, add:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### 3. Confirm the scraper still works

Before relying on the schedule, run the **Test seat scrape** workflow
(Actions tab → workflow_dispatch) with a real showtime id — grab one from
`https://www.amctheatres.com/showtimes/<id>/seats` after clicking through
a showtime on AMC's site. It prints a clear pass/fail (including whether
Cloudflare blocked it) and uploads a screenshot + page HTML as a build
artifact either way.

### 4. Enable the monitor workflow

The workflow in `.github/workflows/monitor.yml` runs every 15 minutes and
can also be triggered manually from the Actions tab (`workflow_dispatch`).
Trigger it manually once after adding secrets to confirm everything is
wired up before relying on the schedule.

## Local development

```bash
pip install -r requirements.txt
playwright install chromium   # only needed for the scraper, not for pytest
pytest                        # unit tests for the filter/diff logic, no network calls
cp .env.example .env          # fill in values, then `set -a; source .env; set +a`
python main.py
```
