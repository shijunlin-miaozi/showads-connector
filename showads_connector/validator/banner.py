from showads_connector.types import BannerIDValidationCode

def validate_banner_id(banner_id: object) -> tuple[bool, BannerIDValidationCode | None, int | None]:
    """
    Validate and parse banner_id to an int in [0, 99].
    - Accepts ints and trimmed numeric strings (e.g., "07", "+5")
    - Rejects bools, floats (e.g., "5.0"), and non-numeric values
    Returns:
      (True, None, value)             on success
      (False, <reason_code>, None)    on failure
    """
    # Accept plain ints but reject bools (bool is a subclass of int)
    if isinstance(banner_id, bool):
        return False, "NOT_AN_INTEGER", None
    
    if isinstance(banner_id, int):
        value = banner_id
        
    elif isinstance(banner_id, str):
        s = banner_id.strip()
        if not s:
            return False, "EMPTY_AFTER_TRIM", None
        try:
            value = int(s)  # accepts "07", "+5"; rejects "5.0", "abc"
        except ValueError:
            return False, "NOT_AN_INTEGER", None
    else:
        # e.g., None, float, Decimal, object -> not an integer
        return False, "NOT_AN_INTEGER", None

    if not (0 <= value <= 99):
        return False, "ID_OUT_OF_RANGE", None

    return True, None, value