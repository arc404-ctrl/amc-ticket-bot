import logging
import sys

from amc_monitor import config, state
from amc_monitor.filters import is_available, showtime_id
from amc_monitor.scrape_utils import ScrapeError
from amc_monitor.seat_scraper import fetch_seat_availability, summarize
from amc_monitor.showtime_scraper import fetch_showtimes_for_range
from amc_monitor.telegram_notify import send_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("amc-monitor")


def _seat_summary_line(sid):
    try:
        seats = fetch_seat_availability(sid)
    except ScrapeError as exc:
        log.warning("could not fetch seat map for showtime %s: %s", sid, exc)
        return None
    summary = summarize(seats)
    return f"{summary['available']}/{summary['total']} seats available"


def main():
    st = state.load_state(config.STATE_FILE)
    notified = set(st.get("notified_ids", []))

    try:
        showtimes = fetch_showtimes_for_range(
            config.MOVIE_SLUG, config.THEATRE_SLUG, config.FORMAT_SLUG, config.DAYS_AHEAD
        )
    except ScrapeError as exc:
        log.error("Showtime scrape error: %s", exc)
        sys.exit(1)

    log.info("Found %d showtimes", len(showtimes))

    new_alerts = 0
    for s in showtimes:
        sid = showtime_id(s)
        if sid in notified or not is_available(s):
            continue

        text_lines = [
            "Tickets available!",
            f"Odyssey — {config.FORMAT_SLUG}",
            config.THEATRE_NAME,
            s.get("when") or "unknown time",
        ]
        seat_line = _seat_summary_line(sid)
        if seat_line:
            text_lines.append(seat_line)
        text = "\n".join(text_lines)

        try:
            send_message(text)
        except Exception as exc:
            log.error("Failed to send Telegram alert for showtime %s: %s", sid, exc)
            continue
        notified.add(sid)
        new_alerts += 1
        log.info("Notified for showtime %s", sid)

    if new_alerts:
        state.save_state(config.STATE_FILE, {"notified_ids": sorted(notified)})
        log.info("State updated with %d new notified showtimes", new_alerts)
    else:
        log.info("No new matching showtimes to notify about")


if __name__ == "__main__":
    main()
