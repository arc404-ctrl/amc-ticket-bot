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
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# How many days ahead to poll for showtimes on each run.
DAYS_AHEAD = 21

STATE_FILE = os.environ.get("AMC_STATE_FILE", "state.json")
