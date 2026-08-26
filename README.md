# amc-ticket-bot

Watches AMC Lincoln Square 13 (NYC) for 70mm/IMAX ticket availability for
"Odyssey" and pings a Telegram chat the moment matching tickets go on sale.
Runs on a schedule via GitHub Actions — no server to maintain.

## How it works

1. Polls AMC's official developer API (`api.amctheatres.com`) for showtimes
   at the configured theatre across a rolling window of upcoming days.
2. Filters for showtimes whose title matches `Odyssey` and whose format
   field contains a 70mm/IMAX keyword (see `amc_monitor/config.py`).
3. Diffs against `state.json` (showtime ids already notified about) and
   sends a Telegram message for any new, non-sold-out match.
4. The GitHub Actions workflow commits the updated `state.json` back to the
   branch so re-runs don't send duplicate alerts.

If AMC's catalog API doesn't end up exposing this theatre's showtimes far
enough in advance, `amc_monitor/amc_client.py` is the single place to swap
in a scraping-based fetch — the rest of the pipeline (filter/diff/notify)
stays the same.

## One-time setup

### 1. Get an AMC API vendor key

Request one at
[developers.amctheatres.com/GettingStarted/NewVendorRequest](https://developers.amctheatres.com/GettingStarted/NewVendorRequest).
Catalog/read-only access (showtimes, theatres, movies) doesn't require a
business contract — only ecommerce/purchase endpoints do. This project
only reads showtime data.

### 2. Resolve the theatre id

Once you have a vendor key:

```bash
pip install -r requirements.txt
AMC_VENDOR_KEY=<your key> python scripts/resolve_theatre.py "Lincoln Square"
```

This prints matching theatres from the API — copy the numeric id into
`AMC_THEATRE_ID`. (The exact query parameter/response shape is built from
AMC's published docs rather than a live-tested call, so if this script
doesn't return the theatre, open the API reference at
`developers.amctheatres.com/ApiReference/theatre-api-v2` and adjust
`find_theatre_id` in `amc_monitor/amc_client.py` to match.)

### 3. Telegram bot

You've already created the bot via @BotFather. To get your numeric chat id:

1. Send any message to your bot in Telegram.
2. Run:
   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"
   ```
3. Read `message.chat.id` out of the response.

### 4. Add GitHub Actions secrets

In the repo's Settings → Secrets and variables → Actions, add:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `AMC_VENDOR_KEY`
- `AMC_THEATRE_ID`

### 5. Enable the workflow

The workflow in `.github/workflows/monitor.yml` runs every 15 minutes and
can also be triggered manually from the Actions tab (`workflow_dispatch`).
Trigger it manually once after adding secrets to confirm everything is
wired up before relying on the schedule.

## Local development

```bash
pip install -r requirements.txt
pytest                # unit tests for the filter/diff logic, no network calls
cp .env.example .env  # fill in values, then `set -a; source .env; set +a`
python main.py
```
