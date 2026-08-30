# amc-ticket-bot

Watches AMC Lincoln Square 13 (NYC) for IMAX 70mm showtimes of "Odyssey"
that have decent seats open. When auto-checkout is enabled it buys up to
4 adjacent seats automatically, against a payment method already saved
on the AMC account — the card number and expiry are never entered by
this code, only selected; see [Security](#security) for the one
exception (the card's CVV) and why it's needed. Either way it pings a
Telegram chat with what happened. Runs on a schedule via GitHub Actions
— no server to maintain.

**Auto-checkout automates real purchases with a real account and a real
saved card.** It's off by default (`AMC_AUTO_PURCHASE=false`) and has to
be turned on deliberately after verifying it works — see
[Auto-checkout](#auto-checkout) and [Security](#security) below before
enabling it. This also very likely runs afoul of AMC's terms of service
around automated purchasing; this project is for personal convenience
buying tickets on your own account, not resale.

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
   opened up, more seats freed up, whatever — and the showtime hasn't
   already been bought, it acts:
   - **Auto-checkout on** (`AMC_AUTO_PURCHASE=true`, credentials set):
     picks the best block of up to 4 adjacent seats
     (`amc_monitor/good_seats.py`'s `find_best_seat_block`) and completes
     the order via `amc_monitor/checkout_scraper.py` — sign in, select
     seats, place the order against the card already on the account. The
     showtime is marked purchased so it's never bought again, and this is
     recorded to `state.json` immediately (before the Telegram call, so a
     mid-run crash can't lose it). A Telegram message reports what was
     bought, or that checkout was attempted and failed.
   - **Auto-checkout off** (the default): same as before — a Telegram
     alert listing the seats, nothing purchased.
   No change means no message, even though every non-purchased candidate
   showtime gets re-scraped every run.
5. `state.json` is saved after every showtime that changes, not batched to
   the end of the run — again, so a crash partway through a run can't
   lose a purchase record. The GitHub Actions workflow commits it back to
   the branch (with `if: always()`, so this still happens even if the run
   itself errored out).

This is inherently fragile: it depends on AMC's current page markup and on
patchright continuing to clear Cloudflare's challenge, neither of which is
guaranteed to keep working — Cloudflare evasion is an arms race, and this
already lost round one (plain headless Playwright) after about a day of
traffic. If AMC's markup changes, `showtime_scraper.py` and
`seat_scraper.py` are where to look; if Cloudflare wins again, the real fix
is likely running this from a residential IP (e.g. your own machine)
instead of GitHub-hosted runners, not another stealth library.

Re-scraping every candidate showtime's seat map every run is the expensive
part, and not because of anything in this code: Cloudflare's challenge on
`/showtimes/{id}/seats` specifically (unlike the listing pages, which clear
in under a second) measured at ~30-35s to resolve per showtime, essentially
every time, regardless of browser reuse. At today's ~60 candidates after
the time-of-day filter, that's a ~35-40 minute run — which is why the cron
is hourly, not every 15 minutes. If `DAYS_AHEAD` or the filter widens the
candidate count further, runs will queue up behind each other
(`concurrency.cancel-in-progress: false` in `monitor.yml`) rather than
overlap, but polling will effectively slow down even more. The only real
levers are narrowing which showtimes get checked or accepting a longer
interval — running seat-checks concurrently would cut wall-clock time but
risks the bursty-traffic pattern that triggered the original hard block.

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

The workflow in `.github/workflows/monitor.yml` runs hourly and can also
be triggered manually from the Actions tab (`workflow_dispatch`).
Trigger it manually once after adding secrets to confirm everything is
wired up before relying on the schedule. At this point, with no AMC
secrets set, it runs in notify-only mode.

## Auto-checkout

Off by default. Turning it on lets this bot sign into your AMC account
and place a real order — up to 4 adjacent seats, against the payment
method already saved on the account — the moment good seats show up.
Read this whole section before flipping it on.

**`amc_monitor/checkout_scraper.py` is confirmed end-to-end against the
real site**, including one real completed purchase (2 Odyssey tickets,
order confirmation #0156826682, refunded) — see the module's own
docstring for exactly what was checked. If you want to re-verify before
trusting it further (recommended after any gap in usage, since AMC's
markup can change without notice), use `scripts/check_checkout_flow.py`:

```bash
cp .env.example .env   # fill in AMC_EMAIL / AMC_PASSWORD / AMC_CVV, then `set -a; source .env; set +a`
python scripts/check_checkout_flow.py <showtime_id> --seats A10,A11
```

Run it locally, headed, so you can watch the browser. Without
`--confirm-purchase` it's a dry run: it signs in, selects the given
seats, walks through to the order-review page (selecting a saved card
and confirming the Purchase button is enabled), and stops — no order is
placed, no charge happens. It dumps a screenshot + HTML at every step to
`checkout-flow-debug/`, so you can see exactly where a selector in
`checkout_scraper.py` doesn't match reality and fix it from evidence
rather than guessing. `--confirm-purchase` places a real order — there's
no AMC sandbox, so this is the only way to verify the very last step.

**Things worth knowing from real-site testing:**
- AMC's own checkout API occasionally throws a transient "Error: Failed
  to fetch" partway through, and separately can silently fail to advance
  with no visible error at all — `checkout_scraper.py` retries past both
  automatically.
- AMC re-prompts for the saved card's **CVV** when a purchase hasn't
  happened in a while — expected for this bot's sporadic usage pattern,
  not a one-off. See [Security](#security) below on `AMC_CVV` before
  setting this up.
- The in-page state right after clicking "Purchase" turned out
  unreliable to detect success from (AMC shows a "Now Processing Your
  Order" modal that explicitly warns against navigating away while it's
  up, and an early version of this code moved on before that modal even
  cleared). Success is instead confirmed by reading the order back from
  AMC's own order history page, which is unambiguous.
- If your AMC account has more than one saved card, `checkout_scraper.py`
  always picks the *last* one listed — confirmed correct for two cards
  (one expired, one valid) but not proven as a rule; the reliable fix if
  it's ever wrong is removing stale/expired cards from the account so
  there's only one choice.

Once you trust the flow:

1. Add `AMC_EMAIL`, `AMC_PASSWORD`, and `AMC_CVV` as GitHub Actions
   **secrets** (Settings → Secrets and variables → Actions → Secrets).
2. Add `AMC_AUTO_PURCHASE` as a **variable** set to `true` (same page →
   Variables tab). It's a variable, not a secret, so it's easy to flip
   back to `false` from the GitHub UI to pause auto-buying without
   touching credentials.

From then on, whenever good seats open on a showtime that hasn't already
been bought, the bot buys them instead of just notifying — see step 4 in
[How it works](#how-it-works) for exactly what that does and how it
protects against a duplicate purchase on a crashed/retried run.

**Worth knowing going in:**
- This almost certainly conflicts with AMC's terms of service around
  automated ticket purchasing, even for personal use on your own account.
- A stale/expired AMC session, a changed password, or 2FA on the account
  will make `login()` fail loudly (`CheckoutError`/`LoginError`) rather
  than silently — you'll get a "checkout failed" Telegram message, not a
  missed purchase disguised as nothing happening.
- `AMC_AUTO_PURCHASE=false` (or unset) always falls back to today's
  notify-only behavior, even with credentials configured — it's a
  deliberate two-key gate (credentials + this flag) so adding secrets
  alone can't accidentally turn on real purchasing.

## Security

This bot's account credentials and card security code live in GitHub
Actions secrets, which is a real amount of trust to put in this repo's
access controls. Specifically:

- `AMC_EMAIL` / `AMC_PASSWORD` are the account password — treated the
  same as any other password-in-secrets tradeoff (fresh sign-in each
  run, nothing cached beyond the run).
- **`AMC_CVV` is different and worth pausing on.** A card's CVV is
  meant to prove physical possession of the card at the moment of a
  purchase — PCI-DSS explicitly prohibits merchants from storing it once
  a transaction completes, for exactly this reason. Storing it
  long-term as a repo secret, even a GitHub Actions secret, is a
  deliberate deviation from that norm made *only* because AMC's own
  checkout flow re-prompts for it when purchases are infrequent, and
  there's no way past that prompt otherwise (see
  [Auto-checkout](#auto-checkout)). If that's not a tradeoff you want
  to hold indefinitely, the safer default is leaving `AMC_CVV` unset —
  `checkout_scraper.py` raises a clear `CheckoutError` (not a silent
  failure) when AMC shows the CVV prompt and no CVV is configured, so
  you'd get a "checkout failed, needs attention" Telegram message
  instead of a completed purchase on those runs.
- Card *number* and expiry are never entered anywhere in this code —
  only a payment method already on file is selected — and that
  boundary was kept even while adding CVV support.

## Local development

```bash
pip install -r requirements.txt
patchright install chromium   # only needed for the scraper, not for pytest
pytest                        # unit tests for the filter/diff logic, no network calls
cp .env.example .env          # fill in values, then `set -a; source .env; set +a`
python main.py                # needs a display (headed) -- xvfb-run -a python main.py on a headless machine
```
