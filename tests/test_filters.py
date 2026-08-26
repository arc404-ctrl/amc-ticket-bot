from amc_monitor.filters import is_available, showtime_id


def test_is_available_true_for_almost_full():
    assert is_available({"id": "1", "status": "Almost Full"})


def test_is_available_true_for_promo_plus_status():
    assert is_available({"id": "1", "status": "UP TO 15% OFF, Almost Full"})


def test_is_available_false_for_sold_out():
    assert not is_available({"id": "1", "status": "Sold Out"})
    assert not is_available({"id": "1", "status": "sold out"})


def test_showtime_id():
    assert showtime_id({"id": "145674735"}) == "145674735"
