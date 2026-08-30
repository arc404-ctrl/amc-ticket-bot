from amc_monitor.good_seats import find_best_seat_block, find_good_available_seats


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


def test_block_no_good_seats_returns_empty():
    seats = _grid(available_names=())
    assert find_best_seat_block(seats) == []


def test_block_returns_contiguous_run():
    seats = _grid(available_names=("E10", "E11", "E12"))
    assert find_best_seat_block(seats) == ["E10", "E11", "E12"]


def test_block_caps_at_max_count_and_centers_it():
    # E7-E14 are all within the good column range (7-14) for this grid --
    # an 8-seat run should trim to a centered 4.
    seats = _grid(available_names=tuple(f"E{c}" for c in range(7, 15)))
    assert find_best_seat_block(seats, max_count=4) == ["E9", "E10", "E11", "E12"]


def test_block_prefers_more_central_row_when_runs_tie():
    # Two isolated (non-adjacent) good seats in different good rows --
    # same run length (1), so the more central row wins.
    seats = _grid(available_names=("E7", "G13"))
    assert find_best_seat_block(seats) == ["E7"]


def test_block_ignores_non_adjacent_seats_within_a_row():
    seats = _grid(available_names=("E7", "E14"))
    result = find_best_seat_block(seats)
    assert len(result) == 1
    assert result[0] in ("E7", "E14")
