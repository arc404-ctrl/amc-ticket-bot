# amc-ticket-bot

Watches AMC Lincoln Square 13 (NYC) for IMAX 70mm showtimes of "Odyssey"
that have decent seats open, and pings a Telegram chat when they do. Runs
on a schedule via GitHub Actions — no server to maintain.

## How it works

AMC's developer API (`developers.amctheatres.com`) gates seating and
showtime-listing access behind a contractual approval process with no
self-service option — there's no vendor key that gets you this data. So
this project reads AMC's public website directly instead, via a real
(non-headless) Chromium session run through `patchright` — a Playwright
fork built to evade Cloudflare's bot detection, which plain headless
Playwright got flagged by after about a day of GitHub Actions traffic. No
guarantee this holds either; see `scrape_utils.py`'s docstring.

1. `amc_monitor/showtime_scraper.py` scrapes the movie's showtimes-listing
   page for the configured theatre/format across a rolling window of
   upcoming days.
2. Drops sold-out showtimes and, since the movie is already broadly on
   sale, drops weekday showtimes before 6pm local time too (nobody with a
   normal work schedule can get to a Tuesday 2pm) —
   `amc_monitor/filters.py` is where to change that cutoff.
3. For each remaining showtime, scrapes its seat map
   (`amc_monitor/seat_scraper.py`) and picks out the "good" seats
   (`amc_monitor/good_seats.py`: centrally located by row and column, not
   just anything open — see that module's docstring for the exact
   heuristic).
4. Compares that set of good seats against what `state.json` last recorded
   for the showtime. If it's non-empty and has changed — a showtime just
   opened up, more seats freed up, whatever — sends a Telegram alert
   listing the actual seats. No change means no alert, even though every
   candidate showtime gets re-scraped every run.
5. The GitHub Actions workflow commits the updated `state.json` back to the
   branch.

This is inherently fragile: it depends on AMC's current page markup and on
patchright continuing to clear Cloudflare's challenge, neither of which is
guaranteed to keep working — Cloudflare evasion is an arms race, and this
already lost round one (plain headless Playwright) after about a day of
traffic. If AMC's markup changes, `showtime_scraper.py` and
`seat_scraper.py` are where to look; if Cloudflare wins again, the real fix
is likely running this from a residential IP (e.g. your own machine)
instead of GitHub-hosted runners, not another stealth library.

Re-scraping every candidate showtime's seat map every run is the expensive
part (~7s each) — at today's ~90 total Odyssey/IMAX-70mm showtimes across
21 days, the time-of-day filter is what keeps this from being an
11-minute run every 15 minutes. If `DAYS_AHEAD` or the filter changes and
runs start taking longer than the 15-minute cron interval, runs will queue
up behind each other (`concurrency.cancel-in-progress: false` in
`monitor.yml`) rather than overlap, but polling will effectively slow down.

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
patchright install chromium   # only needed for the scraper, not for pytest
pytest                        # unit tests for the filter/diff logic, no network calls
cp .env.example .env          # fill in values, then `set -a; source .env; set +a`
python main.py                # needs a display (headed) -- xvfb-run -a python main.py on a headless machine
```
