from amc_monitor.filters import format_local_time, is_attendable_time, is_available, showtime_id


def test_is_available_true_for_almost_full():
    assert is_available({"id": "1", "status": "Almost Full"})


def test_is_available_true_for_promo_plus_status():
    assert is_available({"id": "1", "status": "UP TO 15% OFF, Almost Full"})


def test_is_available_false_for_sold_out():
    assert not is_available({"id": "1", "status": "Sold Out"})
    assert not is_available({"id": "1", "status": "sold out"})


def test_showtime_id():
    assert showtime_id({"id": "145674735"}) == "145674735"


def test_is_attendable_time_false_for_weekday_daytime():
    # 2026-08-26 is a Wednesday; 14:00 UTC is 10:00am ET.
    assert not is_attendable_time({"when": "2026-08-26T14:00:00.000Z"})


def test_is_attendable_time_true_for_weekday_evening():
    # Same Wednesday; 22:00 UTC is 6:00pm ET -- right at the cutoff.
    assert is_attendable_time({"when": "2026-08-26T22:00:00.000Z"})


def test_is_attendable_time_true_for_weekend_daytime():
    # 2026-08-29 is a Saturday; 14:00 UTC is 10:00am ET.
    assert is_attendable_time({"when": "2026-08-29T14:00:00.000Z"})


def test_is_attendable_time_true_when_time_unparseable():
    assert is_attendable_time({"when": None})


def test_is_attendable_time_false_for_6am_even_on_weekend():
    # 2026-08-29 is a Saturday; 10:00 UTC is 6:00am ET.
    assert not is_attendable_time({"when": "2026-08-29T10:00:00.000Z"})


def test_format_local_time():
    assert format_local_time({"when": "2026-08-26T22:00:00.000Z"}) == "Wed, Aug 26 at 6:00 PM"
