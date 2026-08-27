"""
Best-effort scrape of AMC's public showtimes-listing page.

https://www.amctheatres.com/movies/{movie_slug}/showtimes
    ?date=YYYY-MM-DD&theatre={theatre_slug}&premium-offering={format_slug}

renders one link per showtime for that day/theatre/format (the
premium-offering param already filters server-side, so every returned
showtime is assumed to match without further client-side filtering):

    <a id="145674735" href="https://www.amctheatres.com/showtimes/145674735">
      <time datetime="2026-08-26T22:00:00.000Z">6:00pm</time>
      <span class="sr-only">Almost Full</span>
    </a>

A day with no showtimes listed yet (not on sale, or outside AMC's booking
window) renders no matching links at all -- that's a normal empty result,
not an error. There's no confirmed example of a sold-out showtime's markup
(everything seen during development was "Almost Full", i.e. still
bookable), so sold-out detection is a best-effort text match on the status
span rather than a verified structural signal.
"""
import logging
import re
import time
from datetime import date, timedelta

from .scrape_utils import ScrapeError, goto_and_settle

log = logging.getLogger("amc-monitor.showtimes")

SHOWTIMES_URL = (
    "https://www.amctheatres.com/movies/{movie_slug}/showtimes"
    "?date={date}&theatre={theatre_slug}&premium-offering={format_slug}"
)
SHOWTIME_LINK_SELECTOR = 'a[href*="/showtimes/"][id]'
SHOWTIME_ID_RE = re.compile(r"^\d+$")


class ShowtimeScrapeError(ScrapeError):
    pass


def _parse_showtime_link(link):
    sid = link.get_attribute("id")
    if not sid or not SHOWTIME_ID_RE.match(sid):
        return None

    time_el = link.query_selector("time")
    when = time_el.get_attribute("datetime") if time_el else None

    status_el = link.query_selector("span.sr-only")
    status = status_el.inner_text().strip() if status_el else ""

    return {"id": sid, "when": when, "status": status}


def _fetch_showtimes_for_date(browser_, movie_slug, theatre_slug, format_slug, day, timeout_ms, debug_dir):
    started = time.monotonic()
    url = SHOWTIMES_URL.format(
        movie_slug=movie_slug,
        date=day.isoformat(),
        theatre_slug=theatre_slug,
        format_slug=format_slug,
    )
    page = goto_and_settle(
        browser_,
        url,
        SHOWTIME_LINK_SELECTOR,
        timeout_ms=timeout_ms,
        debug_dir=debug_dir,
        debug_name=f"showtimes-{day.isoformat()}",
    )
    try:
        links = page.query_selector_all(SHOWTIME_LINK_SELECTOR)
        showtimes = [_parse_showtime_link(link) for link in links]
        log.info("fetched %s in %.1fs (%d showtimes)", day, time.monotonic() - started, len(showtimes))
        return [s for s in showtimes if s is not None]
    finally:
        page.close()


def fetch_showtimes_for_range(browser_, movie_slug, theatre_slug, format_slug, days_ahead, timeout_ms=30000, debug_dir=None):
    """
    Scrapes each of the next `days_ahead` days (starting today) for
    showtimes matching movie/theatre/format, reusing the given browser
    instance (see scrape_utils.browser()) across all the page loads --
    callers should pass one shared browser in from main.py so a whole
    run's worth of pages (listing + every seat map) only pays the
    (expensive, headed) browser-launch cost once. A day that errors (e.g.
    a transient Cloudflare block) is logged and skipped rather than
    failing the whole run -- the next poll will pick it back up.
    """
    today = date.today()
    all_showtimes = []
    for offset in range(days_ahead):
        day = today + timedelta(days=offset)
        try:
            all_showtimes.extend(
                _fetch_showtimes_for_date(browser_, movie_slug, theatre_slug, format_slug, day, timeout_ms, debug_dir)
            )
        except ScrapeError as exc:
            log.warning("skipping %s: %s", day, exc)
    return all_showtimes
