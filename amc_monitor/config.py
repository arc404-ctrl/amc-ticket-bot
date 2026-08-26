import os

AMC_API_BASE = "https://api.amctheatres.com"
AMC_VENDOR_KEY = os.environ.get("AMC_VENDOR_KEY", "")

# Numeric theatre id, resolved once via scripts/resolve_theatre.py and then
# hardcoded here or passed in via the AMC_THEATRE_ID secret/env var.
THEATRE_NAME = "AMC Lincoln Square 13"
THEATRE_ID = os.environ.get("AMC_THEATRE_ID", "")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

MOVIE_KEYWORDS = ["odyssey"]
FORMAT_KEYWORDS = ["70mm", "70 mm", "imax 70mm", "imax70"]

# How many days ahead to poll for showtimes on each run.
DAYS_AHEAD = 21

STATE_FILE = os.environ.get("AMC_STATE_FILE", "state.json")
