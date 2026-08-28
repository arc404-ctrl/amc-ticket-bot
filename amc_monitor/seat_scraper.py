"""
Best-effort scrape of AMC's public seat-selection page.

https://www.amctheatres.com/showtimes/{id}/seats server-renders one
checkbox per seat:

    <input type="checkbox" name="A1" aria-label="Occupied AMC Club Rocker A1" disabled>

`disabled` present means the seat is taken; absent means it's open. The
`name` attribute is the seat label (row letter + number) and `aria-label`
carries the seat type (e.g. "AMC Club Rocker", "Wheelchair Space").

This is inherently fragile: it depends on AMC's current markup, which can
change without notice. If AMC changes their page, this is the one place
that needs updating.
"""
import re

from .scrape_utils import ScrapeError, browser, goto_and_settle  # noqa: F401 (re-exported)
from .scrape_utils import CloudflareBlockedError  # noqa: F401 (re-exported for callers)

SEATS_URL = "https://www.amctheatres.com/showtimes/{showtime_id}/seats"
SEAT_SELECTOR = 'input[type="checkbox"][name]'
SEAT_NAME_RE = re.compile(r"^[A-Z]+\d+$")


class SeatScrapeError(ScrapeError):
    pass


def fetch_seat_availability(browser_, showtime_id, timeout_ms=45000, debug_dir=None):
    """
    Returns a list of {"name", "label", "available"} dicts, one per seat.
    Raises CloudflareBlockedError if the bot check intercepted the request,
    or SeatScrapeError for any other failure to find seat data.

    Takes an already-open browser (see scrape_utils.browser()) rather than
    launching its own. Reusing one browser across many showtimes in a run
    doesn't save much here -- measured in production, Cloudflare's
    challenge on this specific route (unlike the showtime-listing pages)
    takes ~30s to resolve essentially every time regardless of browser
    reuse, which is why the default timeout is higher than
    goto_and_settle's own default: 30s was cutting it exactly at the
    resolution time and relying on query_selector_all() getting lucky a
    moment after wait_for_selector gave up.
    """
    url = SEATS_URL.format(showtime_id=showtime_id)
    page = goto_and_settle(
        browser_, url, SEAT_SELECTOR, timeout_ms=timeout_ms, debug_dir=debug_dir, debug_name=f"seats-{showtime_id}"
    )
    try:
        seat_inputs = page.query_selector_all(SEAT_SELECTOR)
        if not seat_inputs:
            raise SeatScrapeError(
                f"no seat elements found for showtime {showtime_id} "
                f"(page title: {page.title()!r})"
            )

        seats = []
        for el in seat_inputs:
            name = el.get_attribute("name")
            if not name or not SEAT_NAME_RE.match(name):
                continue
            seats.append(
                {
                    "name": name,
                    "label": el.get_attribute("aria-label") or "",
                    "available": el.get_attribute("disabled") is None,
                }
            )

        if not seats:
            raise SeatScrapeError(
                f"seat checkboxes found but none matched expected naming for showtime {showtime_id}"
            )

        return seats
    finally:
        page.close()


def summarize(seats):
    available = [s for s in seats if s["available"]]
    return {
        "total": len(seats),
        "available": len(available),
        "available_seats": [s["name"] for s in available],
    }
