import logging
import sys

from amc_monitor import config, state
from amc_monitor.amc_client import AmcApiError, fetch_upcoming_showtimes
from amc_monitor.filters import is_available, matches_target, showtime_id
from amc_monitor.telegram_notify import send_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("amc-monitor")


def main():
    if not config.THEATRE_ID:
        log.error(
            "AMC_THEATRE_ID is not set. Run scripts/resolve_theatre.py once to "
            "look it up, then add it as a secret/env var."
        )
        sys.exit(1)

    st = state.load_state(config.STATE_FILE)
    notified = set(st.get("notified_ids", []))

    try:
        showtimes = fetch_upcoming_showtimes(config.THEATRE_ID, config.DAYS_AHEAD)
    except AmcApiError as exc:
        log.error("AMC API error: %s", exc)
        sys.exit(1)

    log.info("Fetched %d showtimes", len(showtimes))

    matches = [s for s in showtimes if matches_target(s)]
    log.info("%d showtimes match movie/format filters", len(matches))

    new_alerts = 0
    for s in matches:
        sid = showtime_id(s)
        if sid in notified or not is_available(s):
            continue

        when = s.get("showDateTimeLocal") or s.get("showDateTimeUtc") or "unknown time"
        fmt = s.get("premiumFormat") or s.get("format") or ""
        text = (
            f"Tickets available!\n"
            f"{s.get('movieName', 'Odyssey')} — {fmt}\n"
            f"{config.THEATRE_NAME}\n"
            f"{when}"
        )
        send_message(text)
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
