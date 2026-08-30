"""
Automation of AMC's checkout flow: sign in, select seats, choose ticket
type/quantity, skip concessions, and complete an order against the
payment method already saved on the account (no card entry -- see
README).

Confirmed end-to-end against the real site 2026-08-28/29, including a
real completed purchase (order confirmation #0156826682, refunded):

    home page -> click "Sign In" (opens a modal; there is no /sign-in
    page, it 404s) -> fill #email/#password -> submit
      -> /showtimes/{id}/seats -> click each seat's <label> (the
         checkbox itself is never Playwright-"visible", so a direct
         click on it always fails -- the wrapping label is what's
         actually clickable) -> click the "Continue" link
      -> /showtimes/{id}/tickets?seats=... -> click "Add Adult Ticket"
         once per seat -> click Continue (transient "Failed to fetch"
         errors were observed here and cleared on retry -- see
         _click_continue)
      -> /orders/{uuid}/food-and-drink -> click Continue to skip
      -> /orders/{uuid}/purchase ("Confirm Purchase") -> select a saved
         card (Purchase stays disabled until one is picked -- see
         _select_payment_method) -> click Purchase -> handle a CVV
         re-verification modal if AMC shows one (see _maybe_verify_cvv)
         -> wait out AMC's "Now Processing Your Order" modal (see
         _wait_for_order_processing) -> confirm via order history (see
         _fetch_latest_order_confirmation).

Two things worth knowing from that real run: AMC's in-page state right
after clicking Purchase turned out unreliable to key success off of (a
"Confirmation" text match false-positived on unrelated boilerplate text
present on the page even before checkout completes -- fixed by reading
the result back from order history instead, which is unambiguous), and
AMC re-challenges for the card's CVV when a purchase hasn't happened in
a while, which is expected for this bot's sporadic usage pattern.

There's also a visible countdown (~7 minutes, starting from seat
selection) before AMC releases the held seats -- comfortably more than
this flow needs even with a retry or two, but worth knowing if timeouts
are ever widened.

Deliberately never captures a debug screenshot/HTML dump of the sign-in
page, even when debug_dir is set -- avoids ever writing a filled-in
password field into a saved artifact. Capture starts once seat selection
begins.
"""
import re

from patchright.sync_api import TimeoutError as PlaywrightTimeoutError

from .scrape_utils import CHALLENGE_TITLE_MARKERS, CloudflareBlockedError, ScrapeError, save_debug_artifacts

HOME_URL = "https://www.amctheatres.com/"
SEATS_URL = "https://www.amctheatres.com/showtimes/{showtime_id}/seats"

# There is no dedicated /sign-in page (it 404s) -- signing in is a modal
# opened from the "Sign In" control in the site nav.
SIGN_IN_TRIGGER_TEXT = "Sign In"
EMAIL_SELECTOR = "#email"
PASSWORD_SELECTOR = "#password"
SIGN_IN_SUBMIT_SELECTOR = 'button[type="submit"]:has-text("Sign in")'

SEAT_LABEL_SELECTOR_TEMPLATE = 'label:has(input[name="{seat}"])'
CONTINUE_SELECTOR = 'a:has-text("Continue"), button:has-text("Continue")'
ADD_ADULT_TICKET_SELECTOR = 'button[aria-label="Add Adult Ticket"]'
FOOD_AND_DRINK_MARKER_SELECTOR = "text=Food & Drinks"
ORDER_REVIEW_MARKER_SELECTOR = "text=Confirm Purchase"
# The order-review page doesn't pre-select a saved card -- Purchase stays
# disabled until one of these radios is picked. Confirmed 2026-08-29:
# with two cards on file (one expired), clicking the wrong one leaves
# Purchase disabled with no visible error; see _select_payment_method.
PAYMENT_METHOD_RADIO_SELECTOR = 'input[name="paymentMethod"][value^="walletCreditCard"]'
PLACE_ORDER_SELECTOR = 'button[type="submit"]:has-text("Purchase")'
# AMC re-challenges for the saved card's CVV when a purchase hasn't
# happened in a while -- confirmed 2026-08-29 to trigger on this account
# (expected, given this bot's sporadic usage pattern). The field lives
# inside a cross-origin Braintree "hosted field" iframe (PCI isolation
# on AMC's end), hence frame_locator rather than a normal page selector.
CVV_MODAL_MARKER_SELECTOR = "text=Verify Credit Card CVV"
CVV_IFRAME_SELECTOR = 'iframe[name="braintree-hosted-field-cvv"]'
CVV_VERIFY_SELECTOR = 'button[type="submit"]:has-text("Verify")'
# AMC shows this after Purchase, explicitly warning that closing or
# refreshing the page while it's up "could cause your order to
# duplicate, or wind up on the cutting room floor" -- confirmed
# 2026-08-29 this really does appear, and an early version of this
# module returned "success" on a coincidental text match while this
# modal was still on screen. The order happened to complete anyway that
# time, but nothing here should rely on that again -- see
# _wait_for_order_processing.
PROCESSING_MODAL_MARKER_SELECTOR = "text=Now Processing Your Order"
# In-page post-purchase state turned out unreliable to key off of (see
# above), so confirmation is instead read back from AMC's own order
# history, which reliably renders "Ticket Confirmation #: <number>" for
# a completed order -- confirmed against a real completed purchase.
ORDER_HISTORY_URL = "https://www.amctheatres.com/my-amc/history"
TICKET_CONFIRMATION_SELECTOR = "h3:has-text('Ticket Confirmation #:')"
CONFIRMATION_NUMBER_RE = re.compile(r"Ticket Confirmation #:\s*(\S+)", re.IGNORECASE)

ERROR_MODAL_SELECTOR = "text=Error"


class CheckoutError(ScrapeError):
    pass


class LoginError(CheckoutError):
    pass


def _page_title(page):
    try:
        return (page.title() or "").strip()
    except Exception:
        return ""


def _wrap_timeout(page, exc, step, debug_dir=None, debug_name=None):
    title = _page_title(page)
    if debug_dir and debug_name:
        save_debug_artifacts(page, debug_dir, debug_name)
    if any(marker in title.lower() for marker in CHALLENGE_TITLE_MARKERS):
        return CloudflareBlockedError(f"blocked by Cloudflare challenge during {step} (page title: {title!r})")
    return CheckoutError(f"{step} failed (page title: {title!r})")


def login(browser_, email, password, timeout_ms=30000):
    """
    Signs in on a fresh page in `browser_` and returns that page (left
    open, so navigating it onward reuses the authenticated session).
    Raises LoginError on bad/missing credentials or an unrecognized page,
    CloudflareBlockedError if the bot challenge intercepted the request.
    Never writes debug artifacts for this page -- see module docstring.
    """
    if not email or not password:
        raise LoginError("AMC email/password not configured")

    page = browser_.new_page()
    page.goto(HOME_URL, timeout=timeout_ms, wait_until="domcontentloaded")
    sign_in_trigger = page.get_by_text(SIGN_IN_TRIGGER_TEXT, exact=True).first
    try:
        sign_in_trigger.click(timeout=timeout_ms)
        page.wait_for_selector(EMAIL_SELECTOR, timeout=timeout_ms)
        page.fill(EMAIL_SELECTOR, email)
        page.fill(PASSWORD_SELECTOR, password)
        page.click(SIGN_IN_SUBMIT_SELECTOR)
        # The signed-in nav (account name, "Sign Out", etc.) only renders
        # inside a menu that's hidden until opened, so it can't be waited
        # on directly -- the modal closing (password field detaching) is
        # what actually signals success or failure here.
        page.wait_for_selector(PASSWORD_SELECTOR, state="detached", timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        wrapped = _wrap_timeout(page, exc, "sign-in")
        page.close()
        raise wrapped from exc

    if sign_in_trigger.is_visible():
        page.close()
        raise LoginError("sign-in did not appear to succeed (Sign In control still visible after submit)")
    return page


def _select_seats(page, seat_names, timeout_ms, debug_dir):
    for seat in seat_names:
        selector = SEAT_LABEL_SELECTOR_TEMPLATE.format(seat=seat)
        try:
            page.click(selector, timeout=timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise _wrap_timeout(page, exc, f"selecting seat {seat}", debug_dir, "select-seats-failed") from exc
    if debug_dir:
        save_debug_artifacts(page, debug_dir, "seats-selected")


def _click_continue(page, click_selector, marker_selector, step_name, timeout_ms, debug_dir, debug_name, attempts=4):
    """
    Clicks `click_selector` (normally the flow's "Continue" control) and
    waits for `marker_selector` to confirm the next step loaded. AMC's
    own checkout API has been seen to fail transiently -- sometimes with
    a visible "Error: Failed to fetch" dialog, sometimes just silently
    not advancing -- and succeed on a same-page retry, so this dismisses
    an error dialog when there is one and retries either way before
    giving up.
    """
    last_exc = None
    for _ in range(attempts):
        try:
            page.click(click_selector, timeout=timeout_ms)
            page.wait_for_selector(marker_selector, timeout=timeout_ms)
            last_exc = None
            break
        except PlaywrightTimeoutError as exc:
            last_exc = exc
            error_modal = page.query_selector(ERROR_MODAL_SELECTOR)
            if error_modal and error_modal.is_visible():
                close_btn = page.query_selector(f"{ERROR_MODAL_SELECTOR} >> xpath=ancestor::*[1]//button")
                if close_btn:
                    close_btn.click()
            page.wait_for_timeout(1000)

    if last_exc:
        raise _wrap_timeout(page, last_exc, step_name, debug_dir, f"{debug_name}-failed") from last_exc
    if debug_dir:
        # marker_selector resolving only means the heading is in the DOM,
        # not that the rest of the page (order details, payment section)
        # has finished rendering -- a brief settle avoids capturing a
        # loading-spinner screenshot instead of the useful state.
        page.wait_for_timeout(1500)
        save_debug_artifacts(page, debug_dir, debug_name)


def _select_payment_method(page, timeout_ms, debug_dir):
    """
    Picks a saved card so the Purchase button can become enabled -- the
    order-review page never pre-selects one. Confirmed 2026-08-29: with
    two cards on the test account (an expired Visa and a valid
    MasterCard), the *last* card in the list was the one that actually
    unlocked Purchase; the first (expired) one left it silently disabled
    with no visible error. This always picks the last one on that same
    assumption -- if it ever turns out wrong for a different account,
    the fix is either smarter selection here or, more simply, removing
    stale/expired cards from the AMC account so there's only one choice.
    Raises CheckoutError if there's no saved card at all.
    """
    try:
        page.wait_for_selector(PAYMENT_METHOD_RADIO_SELECTOR, state="attached", timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        raise _wrap_timeout(page, exc, "finding a saved payment method", debug_dir, "no-payment-method") from exc
    radios = page.query_selector_all(PAYMENT_METHOD_RADIO_SELECTOR)
    if not radios:
        raise CheckoutError("No saved card found on the AMC account -- add one via amctheatres.com and retry.")
    radios[-1].check(force=True, timeout=timeout_ms)


def _maybe_verify_cvv(page, cvv, timeout_ms, debug_dir):
    """
    Handles AMC's CVV re-verification modal if (and only if) it appears
    after clicking Purchase -- not every purchase triggers it, so this
    returns immediately if the modal never shows up within a short wait.
    Never captures debug artifacts while the modal is open, even though
    the CVV field itself is in a cross-origin iframe AMC's own page
    can't read -- avoids any chance of a masked-but-still-sensitive
    screenshot of the payment step.
    """
    try:
        page.wait_for_selector(CVV_MODAL_MARKER_SELECTOR, timeout=5000)
    except PlaywrightTimeoutError:
        return

    if not cvv:
        raise CheckoutError("AMC is requiring CVV re-verification but AMC_CVV is not configured.")

    try:
        page.frame_locator(CVV_IFRAME_SELECTOR).locator("input").first.fill(cvv, timeout=timeout_ms)
        page.click(CVV_VERIFY_SELECTOR, timeout=timeout_ms)
        page.wait_for_selector(CVV_MODAL_MARKER_SELECTOR, state="detached", timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        raise _wrap_timeout(page, exc, "verifying CVV", debug_dir, "cvv-verify-failed") from exc


def _wait_for_order_processing(page, timeout_ms, debug_dir):
    """
    Waits out AMC's "Now Processing Your Order" modal, if it appears, so
    nothing here ever navigates away or returns control while AMC itself
    warns that doing so risks a duplicate or broken order -- see
    PROCESSING_MODAL_MARKER_SELECTOR.
    """
    try:
        page.wait_for_selector(PROCESSING_MODAL_MARKER_SELECTOR, timeout=5000)
    except PlaywrightTimeoutError:
        return  # didn't show this time
    try:
        page.wait_for_selector(PROCESSING_MODAL_MARKER_SELECTOR, state="detached", timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        raise _wrap_timeout(page, exc, "waiting for order processing to finish", debug_dir, "still-processing") from exc


def _fetch_latest_order_confirmation(page, timeout_ms):
    """
    Confirms the purchase actually completed by reading it back from
    AMC's own order history rather than trusting in-page state
    immediately after clicking Purchase (proven unreliable -- see
    PROCESSING_MODAL_MARKER_SELECTOR). Returns None if no confirmation
    number is found there within the timeout; callers should treat that
    as "status unknown", not "definitely failed" -- the order may still
    have gone through even if this lookup itself has a hiccup.
    """
    page.goto(ORDER_HISTORY_URL, timeout=timeout_ms, wait_until="domcontentloaded")
    try:
        page.wait_for_selector(TICKET_CONFIRMATION_SELECTOR, timeout=timeout_ms)
    except PlaywrightTimeoutError:
        return None
    text = page.inner_text(TICKET_CONFIRMATION_SELECTOR, timeout=5000)
    match = CONFIRMATION_NUMBER_RE.search(text or "")
    return match.group(1) if match else None


def purchase_seats(browser_, showtime_id, seat_names, email, password, cvv, *, dry_run, debug_dir=None, timeout_ms=45000):
    """
    Signs in, selects `seat_names` on the showtime's seat map, picks that
    many Adult tickets, skips concessions, and proceeds to the
    order-review page (payment uses whatever card is already saved on
    the account -- this never enters card *number* data; `cvv` exists
    only for AMC's occasional re-verification challenge, see
    _maybe_verify_cvv).

    If `dry_run` is True, stops at order review and returns None without
    placing the order -- the safe path for verifying the flow with zero
    purchase risk (see scripts/check_checkout_flow.py). If `dry_run` is
    False, clicks the final purchase control (handling a CVV
    re-verification prompt if AMC shows one) and returns
    {"seats": [...], "confirmation": <best-effort order number or None>}.
    Raises CheckoutError immediately, without clicking, if the purchase
    control is disabled (e.g. no payment method on file).

    Raises LoginError, CheckoutError, or CloudflareBlockedError on
    failure. Captures a screenshot + HTML to `debug_dir` at each step
    from seat selection onward (never on the sign-in page itself).
    """
    if not seat_names:
        raise CheckoutError("no seats to purchase")

    page = login(browser_, email, password, timeout_ms=timeout_ms)
    try:
        page.goto(SEATS_URL.format(showtime_id=showtime_id), timeout=timeout_ms, wait_until="domcontentloaded")
        _select_seats(page, seat_names, timeout_ms, debug_dir)

        try:
            page.click(CONTINUE_SELECTOR, timeout=timeout_ms)
            page.wait_for_selector(ADD_ADULT_TICKET_SELECTOR, timeout=timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise _wrap_timeout(page, exc, "proceeding to ticket selection", debug_dir, "checkout-started") from exc
        if debug_dir:
            page.wait_for_timeout(1500)
            save_debug_artifacts(page, debug_dir, "checkout-started")

        for _ in seat_names:
            page.click(ADD_ADULT_TICKET_SELECTOR, timeout=timeout_ms)

        _click_continue(
            page, CONTINUE_SELECTOR, FOOD_AND_DRINK_MARKER_SELECTOR,
            "selecting ticket type", timeout_ms, debug_dir, "food-and-drink",
        )
        _click_continue(
            page, CONTINUE_SELECTOR, ORDER_REVIEW_MARKER_SELECTOR,
            "skipping concessions", timeout_ms, debug_dir, "order-review",
        )

        # ORDER_REVIEW_MARKER_SELECTOR (the page heading) resolves well
        # before the payment section -- including the Purchase button --
        # finishes loading, so wait for the button itself before treating
        # the page as settled (matters for dry_run's debug screenshot too,
        # not just the disabled-check below).
        try:
            page.wait_for_selector(PLACE_ORDER_SELECTOR, state="attached", timeout=timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise _wrap_timeout(page, exc, "locating purchase button", debug_dir, "purchase-not-found") from exc

        _select_payment_method(page, timeout_ms, debug_dir)
        page.wait_for_timeout(1500)  # let the disabled state react to the selection
        if debug_dir:
            save_debug_artifacts(page, debug_dir, "order-review")

        if dry_run:
            return None

        purchase_button = page.query_selector(PLACE_ORDER_SELECTOR)
        if purchase_button.get_attribute("disabled") is not None:
            if debug_dir:
                save_debug_artifacts(page, debug_dir, "purchase-button-disabled")
            raise CheckoutError(
                "Purchase button is still disabled after selecting a saved card -- "
                "check the AMC account's saved payment methods (e.g. an expired card "
                "picked instead of a valid one) and retry."
            )

        try:
            page.click(PLACE_ORDER_SELECTOR, timeout=timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise _wrap_timeout(page, exc, "placing order", debug_dir, "purchase-click-failed") from exc

        _maybe_verify_cvv(page, cvv, timeout_ms, debug_dir)
        _wait_for_order_processing(page, timeout_ms, debug_dir)
        if debug_dir:
            save_debug_artifacts(page, debug_dir, "order-placed")

        confirmation = _fetch_latest_order_confirmation(page, timeout_ms)
        if debug_dir:
            save_debug_artifacts(page, debug_dir, "order-history")

        return {"seats": list(seat_names), "confirmation": confirmation}
    finally:
        page.close()
