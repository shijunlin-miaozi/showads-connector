from showads_connector.validator.banner import validate_banner_id

def test_accepts_int_and_numeric_strings_with_trim():
    ok, code, value = validate_banner_id(42)
    assert ok is True
    assert code is None
    assert value == 42

    ok, code, value = validate_banner_id("42")
    assert ok is True
    assert code is None
    assert value == 42

    ok, code, value = validate_banner_id(" 42 ")
    assert ok is True
    assert code is None
    assert value == 42

    ok, code, value = validate_banner_id("+7")
    assert ok is True
    assert code is None
    assert value == 7

    ok, code, value = validate_banner_id("07")
    assert ok is True
    assert code is None
    assert value == 7

def test_rejects_bool_and_float_and_float_string():
    ok, code, value = validate_banner_id(True)  # bool must be rejected
    assert ok is False
    assert code == "NOT_AN_INTEGER"
    assert value is None

    ok, code, value = validate_banner_id(3.14)
    assert ok is False
    assert code == "NOT_AN_INTEGER"
    assert value is None

    ok, code, value = validate_banner_id("3.0")
    assert ok is False
    assert code == "NOT_AN_INTEGER"
    assert value is None

def test_empty_and_non_numeric():
    ok, code, value = validate_banner_id("")
    assert ok is False
    assert code == "EMPTY_AFTER_TRIM"
    assert value is None

    ok, code, value = validate_banner_id("   ")
    assert ok is False
    assert code == "EMPTY_AFTER_TRIM"
    assert value is None

    ok, code, value = validate_banner_id("abc")
    assert ok is False
    assert code == "NOT_AN_INTEGER"
    assert value is None

def test_range_bounds_inclusive():
    ok, code, value = validate_banner_id(0)
    assert ok is True
    assert code is None
    assert value == 0

    ok, code, value = validate_banner_id(99)
    assert ok is True
    assert code is None
    assert value == 99

def test_out_of_bounds():
    ok, code, value = validate_banner_id(-1)
    assert ok is False
    assert code == "ID_OUT_OF_RANGE"
    assert value is None

    ok, code, value = validate_banner_id(100)
    assert ok is False
    assert code == "ID_OUT_OF_RANGE"
    assert value is None

def test_none_is_not_integer():
    ok, code, value = validate_banner_id(None)
    assert ok is False
    assert code == "NOT_AN_INTEGER"
    assert value is None
