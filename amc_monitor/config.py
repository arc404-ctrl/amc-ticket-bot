import os

# AMC has no self-service API access for showtime/seating data (see
# README) -- these identify the movie/theatre/format on AMC's public
# website, which amc_monitor/showtime_scraper.py and seat_scraper.py
# scrape directly. Confirmed against a real saved page on 2026-08-25:
# https://www.amctheatres.com/movies/the-odyssey-76238/showtimes
#   ?date=2026-08-26&theatre=amc-lincoln-square-13&premium-offering=imax70mm
MOVIE_SLUG = os.environ.get("AMC_MOVIE_SLUG", "the-odyssey-76238")
THEATRE_SLUG = os.environ.get("AMC_THEATRE_SLUG", "amc-lincoln-square-13")
FORMAT_SLUG = os.environ.get("AMC_FORMAT_SLUG", "imax70mm")
THEATRE_NAME = "AMC Lincoln Square 13"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
# Comma-separated to notify more than one chat (e.g. sharing alerts with
# a friend) -- every recipient gets the identical message, including
# purchase attempts.
TELEGRAM_CHAT_IDS = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]

# Auto-checkout: buys against the payment method already saved on the
# AMC account (see README) -- no card number/expiry is ever handled
# here. AMC_CVV is the one exception: AMC re-prompts for the saved
# card's CVV when a purchase hasn't happened in a while (which is
# expected for this bot's usage pattern), and there's no way past that
# prompt without it. Storing a CVV is against PCI norms for a reason --
# this is a deliberate, informed tradeoff for full automation (see
# README's Security section), not something to treat as routine config.
AMC_EMAIL = os.environ.get("AMC_EMAIL", "")
AMC_PASSWORD = os.environ.get("AMC_PASSWORD", "")
AMC_CVV = os.environ.get("AMC_CVV", "")
# Safety gate, default off: even with AMC_EMAIL/AMC_PASSWORD configured,
# main.py only attempts a real purchase when this is explicitly "true".
# Verify amc_monitor/checkout_scraper.py's selectors against the live
# site first via scripts/check_checkout_flow.py (dry-run) -- see README.
AMC_AUTO_PURCHASE = os.environ.get("AMC_AUTO_PURCHASE", "false").lower() == "true"
MAX_SEATS_TO_PURCHASE = 4

# How many days ahead to poll for showtimes on each run.
DAYS_AHEAD = 21

STATE_FILE = os.environ.get("AMC_STATE_FILE", "state.json")
