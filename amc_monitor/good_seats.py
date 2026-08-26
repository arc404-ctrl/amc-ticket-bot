"""
Heuristic for "decent" seats: centrally located (not jammed against the
front, back, or side walls) and actually available right now.

Seat names from seat_scraper.py are "{row letters}{column number}"
(e.g. "G14"). For each row present in the auditorium, this trims off the
front/back ROW_BUFFER_RATIO of rows and, within the remaining rows, the
left/right COLUMN_BUFFER_RATIO of that row's seats -- what's left is
"central" by construction. Tunable, not verified against AMC's own idea
of a good seat (there isn't one to verify against).
"""
import re
from collections import defaultdict

SEAT_NAME_RE = re.compile(r"^([A-Za-z]+)(\d+)$")
EXCLUDED_LABEL_MARKERS = ("wheelchair",)

ROW_BUFFER_RATIO = 0.3
COLUMN_BUFFER_RATIO = 0.3


def _row_value(row_letters):
    # Base-26 so multi-letter rows (AA, AB, ...) still sort correctly,
    # though every AMC auditorium seen so far uses single letters.
    value = 0
    for ch in row_letters.upper():
        value = value * 26 + (ord(ch) - ord("A") + 1)
    return value


def _parse(seats):
    parsed = []
    for seat in seats:
        m = SEAT_NAME_RE.match(seat.get("name") or "")
        if not m:
            continue
        row_letters, col_str = m.groups()
        label = (seat.get("label") or "").lower()
        if any(marker in label for marker in EXCLUDED_LABEL_MARKERS):
            continue
        parsed.append(
            {
                "name": seat["name"],
                "available": seat.get("available", False),
                "row_value": _row_value(row_letters),
                "column": int(col_str),
            }
        )
    return parsed


def find_good_available_seats(seats):
    """Returns a sorted list of seat names that are central and available."""
    parsed = _parse(seats)
    if not parsed:
        return []

    row_values = sorted({s["row_value"] for s in parsed})
    min_row, max_row = row_values[0], row_values[-1]
    row_buffer = max(1, max_row - min_row) * ROW_BUFFER_RATIO
    good_rows = {v for v in row_values if min_row + row_buffer <= v <= max_row - row_buffer}

    columns_by_row = defaultdict(list)
    for s in parsed:
        columns_by_row[s["row_value"]].append(s["column"])

    good = []
    for s in parsed:
        if not s["available"] or s["row_value"] not in good_rows:
            continue
        columns = columns_by_row[s["row_value"]]
        min_col, max_col = min(columns), max(columns)
        col_buffer = max(1, max_col - min_col) * COLUMN_BUFFER_RATIO
        if min_col + col_buffer <= s["column"] <= max_col - col_buffer:
            good.append(s["name"])

    return sorted(good, key=lambda n: (SEAT_NAME_RE.match(n).group(1), int(SEAT_NAME_RE.match(n).group(2))))
