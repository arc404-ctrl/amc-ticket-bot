from amc_monitor.filters import is_available, matches_target, showtime_id


def test_matches_target_true_for_70mm_odyssey():
    showtime = {"movieName": "Odyssey", "premiumFormat": "70mm IMAX", "isSoldOut": False}
    assert matches_target(showtime)


def test_matches_target_false_for_wrong_movie():
    showtime = {"movieName": "Some Other Movie", "premiumFormat": "70mm IMAX"}
    assert not matches_target(showtime)


def test_matches_target_false_for_wrong_format():
    showtime = {"movieName": "Odyssey", "premiumFormat": "Standard Digital"}
    assert not matches_target(showtime)


def test_is_available():
    assert is_available({"isSoldOut": False})
    assert not is_available({"isSoldOut": True})


def test_showtime_id_prefers_explicit_id():
    assert showtime_id({"id": 123}) == "123"
    assert showtime_id({"showtimeId": "abc"}) == "abc"
    fallback = {"movieName": "Odyssey", "showDateTimeLocal": "2026-09-01T19:00:00"}
    assert showtime_id(fallback) == "Odyssey-2026-09-01T19:00:00"
