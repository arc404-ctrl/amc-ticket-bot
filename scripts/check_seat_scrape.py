"""
Diagnostic: confirm the Playwright seat scraper can actually reach
AMC's seat-selection page and clear Cloudflare from wherever this runs
(this matters most from GitHub Actions, since that's where the real
monitor will execute it).

Usage:
    python scripts/check_seat_scrape.py <showtime_id>

Exits non-zero and prints a clear reason on failure (Cloudflare block vs.
markup mismatch vs. other error) so the GitHub Actions log makes the
outcome obvious at a glance.
"""
import sys

sys.path.insert(0, ".")

from amc_monitor.good_seats import find_good_available_seats  # noqa: E402
from amc_monitor.scrape_utils import browser  # noqa: E402
from amc_monitor.seat_scraper import (  # noqa: E402
    CloudflareBlockedError,
    SeatScrapeError,
    fetch_seat_availability,
    summarize,
)


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/check_seat_scrape.py <showtime_id>")
        sys.exit(2)

    showtime_id = sys.argv[1]
    debug_dir = "seat-scrape-debug"
    print(f"Fetching seat map for showtime {showtime_id}...")
    print(f"(screenshot + page HTML will be saved to {debug_dir}/ regardless of outcome)")

    try:
        with browser() as b:
            seats = fetch_seat_availability(b, showtime_id, debug_dir=debug_dir)
    except CloudflareBlockedError as exc:
        print(f"BLOCKED by Cloudflare: {exc}")
        sys.exit(1)
    except SeatScrapeError as exc:
        print(f"FAILED: {exc}")
        sys.exit(1)

    summary = summarize(seats)
    print(f"OK: {summary['total']} seats total, {summary['available']} available")
    if summary["available_seats"]:
        print("Available:", ", ".join(summary["available_seats"][:40]))
    sample = seats[:5]
    print("Sample seats:", sample)

    good = find_good_available_seats(seats)
    print(f"Good (central + available) seats: {len(good)}")
    if good:
        print("Good seats:", ", ".join(good))


if __name__ == "__main__":
    main()
