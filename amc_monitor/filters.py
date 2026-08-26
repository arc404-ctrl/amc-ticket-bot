from . import config


def _get_title(showtime):
    return (showtime.get("movieName") or showtime.get("title") or showtime.get("name") or "").lower()


def _get_format(showtime):
    parts = [showtime.get("premiumFormat"), showtime.get("format"), showtime.get("presentationFormat")]
    return " ".join(str(p) for p in parts if p).lower()


def matches_target(showtime):
    title = _get_title(showtime)
    fmt = _get_format(showtime)
    title_match = any(k in title for k in config.MOVIE_KEYWORDS)
    format_match = any(k in fmt for k in config.FORMAT_KEYWORDS)
    return title_match and format_match


def is_available(showtime):
    return not showtime.get("isSoldOut", False)


def showtime_id(showtime):
    if showtime.get("id"):
        return str(showtime["id"])
    if showtime.get("showtimeId"):
        return str(showtime["showtimeId"])
    # No stable id in the payload -- build one from enough fields that two
    # distinct showtimes at the same time (different format/auditorium)
    # don't collide and silently shadow each other.
    when = showtime.get("showDateTimeLocal") or showtime.get("showDateTimeUtc") or ""
    auditorium = showtime.get("auditorium") or showtime.get("auditoriumNumber") or ""
    return f"{showtime.get('movieName')}|{when}|{_get_format(showtime)}|{auditorium}"
