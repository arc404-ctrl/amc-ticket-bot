"""
Shared browser-automation plumbing for scraping AMC's public website.

AMC's developer API gates seating and (in practice) reliable showtime
listings behind a contractual approval process with no self-service option
(see README). Everything under amc_monitor/*_scraper.py instead reads the
same pages a browser would, which means going through Cloudflare's bot
check. Plain headless Playwright cleared it initially but got flagged into
a hard "Attention Required!" challenge after a day of GitHub Actions
traffic -- that's an IP-reputation problem as much as a fingerprinting one
(GitHub-hosted runners are a well-known datacenter range), so this uses
patchright (a patched, actively-maintained Playwright fork built to evade
this kind of detection) run headed via Xvfb rather than plain headless
Playwright -- patchright's own guidance is that headless mode defeats the
point since Cloudflare's challenge relies on a cookie that a real browser
session earns. See .github/workflows/*.yml for the Xvfb wrapper. None of
this is guaranteed to keep working -- it's an arms race, not a fix.
"""
import logging
import os
import tempfile
from contextlib import contextmanager

from patchright.sync_api import TimeoutError as PlaywrightTimeoutError
from patchright.sync_api import sync_playwright

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
    """
    One persistent, headed Chromium context, reused across multiple page
    loads. Persistent + headed is patchright's own recommendation for
    actually clearing Cloudflare's challenge -- a plain headless
    launch()/new_page() (what this used before) is easier to fingerprint
    and can't hold onto the challenge-solution cookie the way a real
    browser session does.
    """
    with sync_playwright() as p:
        with tempfile.TemporaryDirectory() as user_data_dir:
            context = p.chromium.launch_persistent_context(user_data_dir, headless=False)
            try:
                yield context
            finally:
                context.close()


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
