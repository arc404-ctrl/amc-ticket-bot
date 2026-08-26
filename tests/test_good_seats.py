from amc_monitor.good_seats import find_good_available_seats


def _grid(rows="ABCDEFGHIJ", cols=range(1, 21), available_names=()):
    seats = []
    for row in rows:
        for col in cols:
            name = f"{row}{col}"
            seats.append(
                {
                    "name": name,
                    "label": f"Standard {name}",
                    "available": name in available_names,
                }
            )
    return seats


def test_no_available_seats_returns_empty():
    seats = _grid(available_names=())
    assert find_good_available_seats(seats) == []


def test_center_seat_available_is_good():
    seats = _grid(available_names=("E10",))
    assert find_good_available_seats(seats) == ["E10"]


def test_front_row_edge_seat_is_not_good():
    seats = _grid(available_names=("A1",))
    assert find_good_available_seats(seats) == []


def test_back_row_available_center_column_is_not_good():
    # Row J is the last row -- outside the row buffer even though the
    # column is dead center.
    seats = _grid(available_names=("J10",))
    assert find_good_available_seats(seats) == []


def test_center_row_far_side_column_is_not_good():
    seats = _grid(available_names=("E1",))
    assert find_good_available_seats(seats) == []


def test_wheelchair_labeled_seat_excluded_even_if_central():
    seats = _grid(available_names=("E10",))
    for seat in seats:
        if seat["name"] == "E10":
            seat["label"] = "Wheelchair Space E10"
    assert find_good_available_seats(seats) == []


def test_unavailable_center_seat_is_not_returned():
    seats = _grid(available_names=())
    assert find_good_available_seats(seats) == []


def test_ignores_seats_with_unparseable_names():
    seats = _grid(available_names=("E10",))
    seats.append({"name": "not-a-seat", "label": "", "available": True})
    assert find_good_available_seats(seats) == ["E10"]
