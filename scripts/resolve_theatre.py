"""
One-time helper: resolve AMC Lincoln Square 13's numeric theatre id.

Usage:
    AMC_VENDOR_KEY=... python scripts/resolve_theatre.py "Lincoln Square"

Prints matching theatres so you can copy the id into AMC_THEATRE_ID.
"""
import sys

sys.path.insert(0, ".")

from amc_monitor.amc_client import find_theatre_id  # noqa: E402


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "Lincoln Square"
    for theatre in find_theatre_id(query):
        print(theatre)


if __name__ == "__main__":
    main()
