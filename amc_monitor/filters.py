SOLD_OUT_MARKERS = ("sold out",)


def is_available(showtime):
    status = (showtime.get("status") or "").lower()
    return not any(marker in status for marker in SOLD_OUT_MARKERS)


def showtime_id(showtime):
    return str(showtime["id"])
