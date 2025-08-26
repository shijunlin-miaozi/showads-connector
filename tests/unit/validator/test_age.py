from showads_connector.validator.age import validate_age

CFG = {"min_age": 18, "max_age": 120}

def test_accepts_int():
    ok, code, value = validate_age(25, CFG)
    assert ok is True
    assert code is None
    assert value == 25

def test_accepts_numeric_string_with_spaces():
    ok, code, value = validate_age(" 42 ", CFG)
    assert ok is True
    assert code is None
    assert value == 42

def test_accepts_leading_plus():
    ok, code, value = validate_age("+20", CFG)
    assert ok is True
    assert code is None
    assert value == 20

def test_rejects_bool():
    ok, code, value = validate_age(True, CFG)  # bool is a subclass of int → should be rejected
    assert ok is False
    assert code == "NOT_AN_INTEGER"
    assert value is None

def test_rejects_float_and_float_string():
    ok, code, value = validate_age(5.0, CFG)
    assert ok is False
    assert code == "NOT_AN_INTEGER"
    assert value is None

    ok, code, value = validate_age("5.0", CFG)
    assert ok is False
    assert code == "NOT_AN_INTEGER"
    assert value is None

def test_rejects_non_numeric_and_empty():
    ok, code, value = validate_age("abc", CFG)
    assert ok is False
    assert code == "NOT_AN_INTEGER"
    assert value is None

    ok, code, value = validate_age("   ", CFG)
    assert ok is False
    assert code == "EMPTY_AFTER_TRIM"
    assert value is None

def test_range_bounds_inclusive():
    ok, code, value = validate_age(18, CFG)
    assert ok is True
    assert code is None
    assert value == 18

    ok, code, value = validate_age(120, CFG)
    assert ok is True
    assert code is None
    assert value == 120

def test_range_out_of_bounds():
    ok, code, value = validate_age(17, CFG)
    assert ok is False
    assert code == "AGE_OUT_OF_RANGE"
    assert value is None

    ok, code, value = validate_age(121, CFG)
    assert ok is False
    assert code == "AGE_OUT_OF_RANGE"
    assert value is None
