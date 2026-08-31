import logging
import sys
import time

from amc_monitor import config, state
from amc_monitor.checkout_scraper import CheckoutError, purchase_seats
from amc_monitor.filters import format_local_time, is_attendable_time, is_available, showtime_id
from amc_monitor.good_seats import find_best_seat_block, find_good_available_seats
from amc_monitor.scrape_utils import ScrapeError
from amc_monitor.scrape_utils import browser as open_browser
from amc_monitor.seat_scraper import fetch_seat_availability
from amc_monitor.showtime_scraper import fetch_showtimes_for_range
from amc_monitor.telegram_notify import send_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("amc-monitor")


def _seats_for(browser_, sid):
    """Returns None (not []) on scrape failure, so callers can leave prior state alone and retry next run."""
    try:
        return fetch_seat_availability(browser_, sid)
    except ScrapeError as exc:
        log.warning("could not fetch seat map for showtime %s: %s", sid, exc)
        return None


def _handle_available_showtime(browser_, s, sid, seats, current, showtime_state):
    """
    Called when showtime `sid` has good seats that are newly available or
    changed. Attempts a purchase if auto-purchase is configured and an
    adjacent seat block is found; otherwise sends the notify-only alert
    this bot always sent. Returns True if it's safe to record `current`
    as the showtime's good_seats state -- False to leave state alone so
    this gets retried next run (mirrors the old "don't update state on
    notify failure" behavior; a successful purchase is always recorded
    regardless of whether the follow-up Telegram alert lands, and a
    failed checkout attempt always returns False so it keeps retrying
    next run instead of going quiet on that showtime).
    """
    entry = showtime_state.setdefault(sid, {})
    block = (
        find_best_seat_block(seats, config.MAX_SEATS_TO_PURCHASE)
        if config.AMC_AUTO_PURCHASE and config.AMC_EMAIL and config.AMC_PASSWORD
        else []
    )

    purchased = False
    checkout_failed = False
    if block:
        try:
            order = purchase_seats(
                browser_, sid, block, config.AMC_EMAIL, config.AMC_PASSWORD, config.AMC_CVV, dry_run=False
            )
        except CheckoutError as exc:
            log.error("Checkout failed for showtime %s: %s", sid, exc)
            checkout_failed = True
            text = (
                f"Good seats open for Odyssey ({config.FORMAT_SLUG}) -- checkout attempt failed: {exc}\n"
                f"{config.THEATRE_NAME}\n"
                f"{format_local_time(s)}\n"
                f"Seats: {', '.join(sorted(current))}\n"
                f"Will retry next run."
            )
        else:
            purchased = True
            entry["purchased"] = True
            entry["order"] = order
            entry["good_seats"] = sorted(current)
            # Saved immediately, before even trying to notify -- a crash
            # between here and the Telegram call must not lose the fact
            # that this showtime was already bought (real money, real
            # risk of a duplicate order next run otherwise).
            state.save_state(config.STATE_FILE, {"showtimes": showtime_state})
            log.info("Purchased showtime %s: %s", sid, order)
            text = (
                f"Bought tickets for Odyssey ({config.FORMAT_SLUG})\n"
                f"{config.THEATRE_NAME}\n"
                f"{format_local_time(s)}\n"
                f"Seats: {', '.join(order['seats'])}\n"
                f"Confirmation: {order.get('confirmation') or 'n/a'}"
            )
    else:
        text = (
            f"Good seats open for Odyssey ({config.FORMAT_SLUG})\n"
            f"{config.THEATRE_NAME}\n"
            f"{format_local_time(s)}\n"
            f"Seats: {', '.join(sorted(current))}"
        )

    try:
        send_message(text)
    except Exception as exc:
        log.error("Failed to send Telegram alert for showtime %s: %s", sid, exc)
        return purchased
    log.info("Notified for showtime %s", sid)
    return purchased or not checkout_failed


def main():
    st = state.load_state(config.STATE_FILE)
    showtime_state = st.get("showtimes", {})

    with open_browser() as b:
        try:
            showtimes = fetch_showtimes_for_range(
                b, config.MOVIE_SLUG, config.THEATRE_SLUG, config.FORMAT_SLUG, config.DAYS_AHEAD
            )
        except ScrapeError as exc:
            log.error("Showtime scrape error: %s", exc)
            sys.exit(1)

        log.info("Found %d showtimes", len(showtimes))

        candidates = [s for s in showtimes if is_available(s) and is_attendable_time(s)]
        log.info("%d showtimes are available and in the attendable time window", len(candidates))

        for s in candidates:
            sid = showtime_id(s)
            if showtime_state.get(sid, {}).get("purchased"):
                continue  # already bought -- skip the (expensive) seat-map scrape entirely

            started = time.monotonic()
            seats = _seats_for(b, sid)
            log.info("checked showtime %s in %.1fs", sid, time.monotonic() - started)
            if seats is None:
                continue  # scrape failed -- leave state as-is, try again next run

            good_seats = find_good_available_seats(seats)
            previous = set(showtime_state.get(sid, {}).get("good_seats", []))
            current = set(good_seats)

            state_update_ok = True
            if current and current != previous:
                state_update_ok = _handle_available_showtime(b, s, sid, seats, current, showtime_state)

            if current != previous and state_update_ok:
                entry = showtime_state.setdefault(sid, {})
                entry["good_seats"] = sorted(current)
                state.save_state(config.STATE_FILE, {"showtimes": showtime_state})

    log.info("Run complete")


if __name__ == "__main__":
    main()
