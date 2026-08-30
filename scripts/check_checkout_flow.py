"""
Diagnostic: walk AMC's real sign-in -> seat-selection -> checkout flow
and confirm checkout_scraper.py's (unverified, best-effort) selectors
actually match the live site.

Safe by default: without --confirm-purchase this runs in dry-run mode,
which stops right before the final "place order" click and never spends
money. It still dumps a screenshot + page HTML at every step to
checkout-flow-debug/, so selector mismatches can be fixed from real
evidence. --confirm-purchase places a real order -- there's no AMC
sandbox, so that's the only way to verify the very last click, and it
will charge the payment method on file.

Usage:
    python scripts/check_checkout_flow.py <showtime_id> --seats A10,A11 [--confirm-purchase]

Requires AMC_EMAIL / AMC_PASSWORD in the environment. AMC_CVV is only
needed for --confirm-purchase, and only if AMC actually shows its CVV
re-verification challenge (not guaranteed every run).
"""
import argparse
import sys

sys.path.insert(0, ".")

from amc_monitor import config  # noqa: E402
from amc_monitor.checkout_scraper import (  # noqa: E402
    CheckoutError,
    CloudflareBlockedError,
    LoginError,
    purchase_seats,
)
from amc_monitor.scrape_utils import browser  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("showtime_id")
    parser.add_argument("--seats", required=True, help="comma-separated seat names, e.g. A10,A11")
    parser.add_argument(
        "--confirm-purchase",
        action="store_true",
        help="place a real order instead of stopping at the dry-run order-review step",
    )
    args = parser.parse_args()

    seat_names = [s.strip() for s in args.seats.split(",") if s.strip()]
    dry_run = not args.confirm_purchase
    debug_dir = "checkout-flow-debug"

    if not config.AMC_EMAIL or not config.AMC_PASSWORD:
        print("FAILED: AMC_EMAIL / AMC_PASSWORD not set in the environment")
        sys.exit(2)

    print(f"{'Dry run' if dry_run else 'REAL PURCHASE'}: showtime {args.showtime_id}, seats {seat_names}")
    print(f"(screenshots + page HTML saved to {debug_dir}/ at each step, regardless of outcome)")
    if not dry_run:
        print("--confirm-purchase set: this WILL place a real order and charge the card on file.")

    try:
        with browser() as b:
            result = purchase_seats(
                b, args.showtime_id, seat_names, config.AMC_EMAIL, config.AMC_PASSWORD, config.AMC_CVV,
                dry_run=dry_run, debug_dir=debug_dir,
            )
    except CloudflareBlockedError as exc:
        print(f"BLOCKED by Cloudflare: {exc}")
        sys.exit(1)
    except LoginError as exc:
        print(f"LOGIN FAILED: {exc}")
        sys.exit(1)
    except CheckoutError as exc:
        print(f"CHECKOUT FAILED: {exc}")
        sys.exit(1)

    if dry_run:
        print("OK: reached order review without error. Inspect the debug artifacts to confirm each step looks right.")
    else:
        print(f"OK: order placed. {result}")


if __name__ == "__main__":
    main()
