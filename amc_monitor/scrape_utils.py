"""
Shared Playwright plumbing for scraping AMC's public website.

AMC's developer API gates seating and (in practice) reliable showtime
listings behind a contractual approval process with no self-service option
(see README). Everything under amc_monitor/*_scraper.py instead reads the
same pages a browser would, which means going through Cloudflare's bot
check -- headless Chromium clears it as of the last check
(see .github/workflows/test-seat-scrape.yml), but that's not guaranteed to
keep working if AMC's protection changes.
"""
import logging
import os
from contextlib import contextmanager

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

log = logging.getLogger("amc-monitor.scrape")

CHALLENGE_TITLE_MARKERS = ("just a moment", "attention required")


class ScrapeError(RuntimeError):
    pass


class CloudflareBlockedError(ScrapeError):
    pass


def _save_debug_artifacts(page, debug_dir, name):
    os.makedirs(debug_dir, exist_ok=True)
    try:
        page.screenshot(path=os.path.join(debug_dir, f"{name}.png"))
    except Exception:
        log.warning("could not capture debug screenshot for %s", name, exc_info=True)
    try:
        with open(os.path.join(debug_dir, f"{name}.html"), "w") as f:
            f.write(page.content())
    except Exception:
        log.warning("could not capture debug html for %s", name, exc_info=True)


@contextmanager
def browser():
    """One headless Chromium instance, reused across multiple page loads."""
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            yield b
        finally:
            b.close()


def goto_and_settle(browser_, url, wait_selector, timeout_ms=30000, debug_dir=None, debug_name="page"):
    """
    Opens a new page in `browser_`, navigates to `url`, and waits for
    `wait_selector` on a best-effort basis (a timeout here isn't itself an
    error -- the caller inspects whatever the page settled into, since
    "no matching elements" can legitimately mean "nothing listed").

    Raises CloudflareBlockedError if the bot challenge intercepted the
    request. Returns the open Page; the caller is responsible for closing
    it once done reading from it.
    """
    page = browser_.new_page()
    page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
    try:
        page.wait_for_selector(wait_selector, timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass

    title = (page.title() or "").strip()

    if debug_dir:
        _save_debug_artifacts(page, debug_dir, debug_name)

    if any(marker in title.lower() for marker in CHALLENGE_TITLE_MARKERS):
        page.close()
        raise CloudflareBlockedError(f"blocked by Cloudflare challenge (page title: {title!r})")

    return page
