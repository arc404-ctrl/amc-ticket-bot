import logging
from datetime import date, timedelta

import requests

from . import config

log = logging.getLogger("amc-monitor.client")


class AmcApiError(RuntimeError):
    pass


def _headers():
    if not config.AMC_VENDOR_KEY:
        raise AmcApiError("AMC_VENDOR_KEY is not set")
    return {"X-AMC-Vendor-Key": config.AMC_VENDOR_KEY, "Accept": "application/json"}


def find_theatre_id(name_substring):
    """
    One-off lookup to resolve a theatre's numeric id by name. Run this manually
    (see scripts/resolve_theatre.py) once you have a vendor key, then hardcode
    the result as AMC_THEATRE_ID. Endpoint per
    https://developers.amctheatres.com/ApiReference/theatre-api-v2 -- verify
    the exact query parameter against the live docs/response, since this is
    built from documentation excerpts rather than a live-tested response.
    """
    resp = requests.get(
        f"{config.AMC_API_BASE}/v2/theatres",
        headers=_headers(),
        params={"name": name_substring},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    theatres = data.get("_embedded", {}).get("theatres", data.get("theatres", []))
    return [t for t in theatres if name_substring.lower() in (t.get("name") or "").lower()]


def fetch_showtimes_for_date(theatre_id, day):
    date_str = day.strftime("%m-%d-%Y")
    url = f"{config.AMC_API_BASE}/v2/theatres/{theatre_id}/showtimes/{date_str}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=15)
    except requests.RequestException as exc:
        raise AmcApiError(f"request failed for {date_str}: {exc}") from exc

    if resp.status_code == 404:
        log.warning(
            "404 for theatre %s on %s -- no showtimes that day, or the date "
            "format/theatre id doesn't match what the API expects",
            theatre_id,
            date_str,
        )
        return []
    if resp.status_code == 429:
        raise AmcApiError("rate limited (429) by AMC API")
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise AmcApiError(f"AMC API error for {date_str}: {exc}") from exc

    data = resp.json()
    return data.get("_embedded", {}).get("showtimes", data.get("showtimes", []))


def fetch_upcoming_showtimes(theatre_id, days_ahead):
    today = date.today()
    all_showtimes = []
    for offset in range(days_ahead):
        day = today + timedelta(days=offset)
        try:
            all_showtimes.extend(fetch_showtimes_for_date(theatre_id, day))
        except AmcApiError as exc:
            log.warning("skipping %s: %s", day, exc)
    return all_showtimes
