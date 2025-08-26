from showads_connector.validator.name import validate_name

def test_ok_basic():
    ok, code, parsed = validate_name("Emily Doe")
    assert ok is True
    assert code is None
    assert parsed == "Emily Doe"

def test_reject_tab_whitespace():
    ok, code, parsed = validate_name("Emily\tDoe")
    assert ok is False
    assert code == "NON_ASCII_WHITESPACE"
    assert parsed is None

def test_reject_double_space():
    ok, code, parsed = validate_name("Emily  Doe")
    assert ok is False
    assert code == "DOUBLE_SPACE"
    assert parsed is None

def test_reject_digit():
    ok, code, parsed = validate_name("Emily3")
    assert ok is False
    assert code == "NON_LETTER_CHAR"
    assert parsed is None

def test_reject_empty_after_trim():
    ok, code, parsed = validate_name("   ")
    assert ok is False
    assert code == "EMPTY_AFTER_TRIM"
    assert parsed is None

def test_reject_not_a_string():
    ok, code, parsed = validate_name(123)
    assert ok is False
    assert code == "NOT_A_STRING"
    assert parsed is None
