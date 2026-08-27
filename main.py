import logging
import sys
import time

from amc_monitor import config, state
from amc_monitor.filters import format_local_time, is_attendable_time, is_available, showtime_id
from amc_monitor.good_seats import find_good_available_seats
from amc_monitor.scrape_utils import ScrapeError
from amc_monitor.scrape_utils import browser as open_browser
from amc_monitor.seat_scraper import fetch_seat_availability
from amc_monitor.showtime_scraper import fetch_showtimes_for_range
from amc_monitor.telegram_notify import send_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("amc-monitor")


def _good_seats_for(browser_, sid):
    """Returns None (not []) on scrape failure, so callers can leave prior state alone and retry next run."""
    try:
        seats = fetch_seat_availability(browser_, sid)
    except ScrapeError as exc:
        log.warning("could not fetch seat map for showtime %s: %s", sid, exc)
        return None
    return find_good_available_seats(seats)


def main():
    st = state.load_state(config.STATE_FILE)
    showtime_state = st.get("showtimes", {})

    changed = False
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
            started = time.monotonic()
            good_seats = _good_seats_for(b, sid)
            log.info("checked showtime %s in %.1fs", sid, time.monotonic() - started)
            if good_seats is None:
                continue  # scrape failed -- leave state as-is, try again next run

            previous = set(showtime_state.get(sid, {}).get("good_seats", []))
            current = set(good_seats)

            if current and current != previous:
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
                    continue  # don't update state -- retry next run
                log.info("Notified for showtime %s: %s", sid, sorted(current))

            if current != previous:
                showtime_state[sid] = {"good_seats": sorted(current)}
                changed = True

    if changed:
        state.save_state(config.STATE_FILE, {"showtimes": showtime_state})
        log.info("State updated")
    else:
        log.info("No changes in good-seat availability")


if __name__ == "__main__":
    main()
