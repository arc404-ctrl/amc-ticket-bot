from datetime import datetime
from zoneinfo import ZoneInfo

SOLD_OUT_MARKERS = ("sold out",)

THEATRE_TIMEZONE = ZoneInfo("America/New_York")
WEEKDAY_EVENING_HOUR = 18  # weekday showtimes before 6pm local are skipped
EXCLUDED_HOURS = {6}  # 6am showtimes are skipped regardless of day


def is_available(showtime):
    status = (showtime.get("status") or "").lower()
    return not any(marker in status for marker in SOLD_OUT_MARKERS)


def showtime_id(showtime):
    return str(showtime["id"])


def _local_datetime(showtime):
    when = showtime.get("when")
    if not when:
        return None
    return datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(THEATRE_TIMEZONE)


def is_attendable_time(showtime):
    """
    True for any weekend showtime, or a weekday showtime at/after 6pm
    local time -- except 6am showtimes, which are always excluded.
    Showtimes with no parseable time are kept rather than silently dropped.
    """
    dt = _local_datetime(showtime)
    if dt is None:
        return True
    if dt.hour in EXCLUDED_HOURS:
        return False
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return True
    return dt.hour >= WEEKDAY_EVENING_HOUR


def format_local_time(showtime):
    dt = _local_datetime(showtime)
    if dt is None:
        return showtime.get("when") or "unknown time"
    return dt.strftime("%a, %b %-d at %-I:%M %p")
