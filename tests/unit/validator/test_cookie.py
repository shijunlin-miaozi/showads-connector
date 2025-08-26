from showads_connector.validator.cookie import validate_cookie

# A known UUID we’ll use across acceptance tests (cannical hyphenated lowercase)
BASE = "123e4567-e89b-12d3-a456-426614174000"

def test_accepts_hyphenated_and_normalizes_case():
    ok, code, val = validate_cookie(BASE.upper())
    assert ok is True
    assert code is None
    assert val == BASE

def test_accepts_32hex_form():
    raw = "123E4567E89B12D3A456426614174000"
    ok, code, val = validate_cookie(raw)
    assert ok is True
    assert code is None
    assert val == BASE

def test_accepts_braced_form_and_trims_spaces():
    raw = f"  {{{BASE}}}  "
    ok, code, val = validate_cookie(raw)
    assert ok is True
    assert code is None
    assert val == BASE

def test_accepts_urn_form():
    raw = f"urn:uuid:{BASE}"
    ok, code, val = validate_cookie(raw)
    assert ok is True
    assert code is None
    assert val == BASE

def test_rejects_nil_uuid():
    ok, code, val = validate_cookie("00000000-0000-0000-0000-000000000000")
    assert ok is False
    assert code == "NIL_UUID"
    assert val is None

def test_rejects_non_string_types():
    ok, code, val = validate_cookie(123)
    assert ok is False
    assert code == "NOT_A_STRING"
    assert val is None

    ok, code, val = validate_cookie(None)
    assert ok is False
    assert code == "NOT_A_STRING"
    assert val is None

def test_rejects_empty_after_trim():
    ok, code, val = validate_cookie("   ")
    assert ok is False
    assert code == "EMPTY_AFTER_TRIM"
    assert val is None

def test_rejects_malformed_uuid():
    # wrong length
    ok, code, val = validate_cookie("1234")
    assert ok is False
    assert code == "BAD_UUID"
    assert val is None

    # bad hex char
    ok, code, val = validate_cookie("g23e4567-e89b-12d3-a456-426614174000")
    assert ok is False
    assert code == "BAD_UUID"
    assert val is None
