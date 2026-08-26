"""
Best-effort scrape of AMC's public seat-selection page.

AMC's official developer API restricts seating/ecommerce endpoints to
partners with a contractual agreement (see README) -- there is no
self-service way to get seat-level availability. This instead loads
https://www.amctheatres.com/showtimes/{id}/seats with a real headless
browser and reads the seat checkboxes AMC renders server-side:

    <input type="checkbox" name="A1" aria-label="Occupied AMC Club Rocker A1" disabled>

`disabled` present means the seat is taken; absent means it's open. The
`name` attribute is the seat label (row letter + number) and `aria-label`
carries the seat type (e.g. "AMC Club Rocker", "Wheelchair Space").

This is inherently fragile: it depends on AMC's current markup and on
Playwright/Chromium clearing Cloudflare's bot check, neither of which is
guaranteed to keep working. If AMC changes their page, this is the one
place that needs updating.
"""
import logging
import os
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

log = logging.getLogger("amc-monitor.seats")

SEATS_URL = "https://www.amctheatres.com/showtimes/{showtime_id}/seats"
SEAT_SELECTOR = 'input[type="checkbox"][name]'

CHALLENGE_TITLE_MARKERS = ("just a moment", "attention required")


class SeatScrapeError(RuntimeError):
    pass


class CloudflareBlockedError(SeatScrapeError):
    pass


def _save_debug_artifacts(page, debug_dir):
    os.makedirs(debug_dir, exist_ok=True)
    try:
        page.screenshot(path=os.path.join(debug_dir, "page.png"), full_page=True)
    except Exception:
        log.warning("could not capture debug screenshot", exc_info=True)
    try:
        with open(os.path.join(debug_dir, "page.html"), "w") as f:
            f.write(page.content())
    except Exception:
        log.warning("could not capture debug html", exc_info=True)


def fetch_seat_availability(showtime_id, timeout_ms=30000, debug_dir=None):
    """
    Returns a list of {"name", "label", "available"} dicts, one per seat.
    Raises CloudflareBlockedError if the bot check intercepted the request,
    or SeatScrapeError for any other failure to find seat data.

    If debug_dir is given, a screenshot and the final page HTML are saved
    there regardless of outcome, for inspecting what actually loaded.
    """
    url = SEATS_URL.format(showtime_id=showtime_id)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            # "networkidle" can hang indefinitely on pages with background
            # polling/analytics that never go quiet; wait for DOM content,
            # then explicitly wait for the seat elements (or time out) below.
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            try:
                page.wait_for_selector(SEAT_SELECTOR, timeout=timeout_ms)
            except PlaywrightTimeoutError:
                pass  # fall through -- inspect whatever the page settled on

            title = (page.title() or "").strip()

            if debug_dir:
                _save_debug_artifacts(page, debug_dir)

            if any(marker in title.lower() for marker in CHALLENGE_TITLE_MARKERS):
                raise CloudflareBlockedError(
                    f"blocked by Cloudflare challenge (page title: {title!r})"
                )

            seat_inputs = page.query_selector_all(SEAT_SELECTOR)
            if not seat_inputs:
                raise SeatScrapeError(
                    f"no seat elements found for showtime {showtime_id} "
                    f"(page title: {title!r})"
                )

            seats = []
            for el in seat_inputs:
                name = el.get_attribute("name")
                if not name or not re.match(r"^[A-Z]+\d+$", name):
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
            browser.close()


def summarize(seats):
    available = [s for s in seats if s["available"]]
    return {
        "total": len(seats),
        "available": len(available),
        "available_seats": [s["name"] for s in available],
    }
