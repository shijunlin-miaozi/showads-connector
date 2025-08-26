from showads_connector.types import AgeValidationCode, AgeConfig

def validate_age(age: object, cfg: AgeConfig) -> tuple[bool, AgeValidationCode | None, int | None]:
    """
    Validate and parse age to an int, within cfg['min_age'] and cfg['max_age'] inclusive.
    Accepts ints and trimmed numeric strings; rejects bools, floats, non-numeric.
    
    Live reload: 
    this function is pure and does not read globals. 
    Pass in the current AgeConfig each time (e.g., pipeline calls cfg.reload_if_needed() and then cfg.age()). 
    Do not cache cfg across rows.
    
    Returns:
      (True, None, value)             on success
      (False, <reason_code>, None)    on failure
    """
    # Accept plain ints but reject bools (bool is a subclass of int)
    if isinstance(age, bool):
        return False, "NOT_AN_INTEGER", None
    
    if isinstance(age, int):
        value = age
        
    elif isinstance(age, str):
        s = age.strip()
        if not s:
            return False, "EMPTY_AFTER_TRIM", None
        try:
            value = int(s)  # accepts "07", "+20"; rejects "5.0", "abc"
        except ValueError:
            return False, "NOT_AN_INTEGER", None
    else:
        # e.g., None, float, Decimal, object -> not an integer
        return False, "NOT_AN_INTEGER", None

    if not (cfg["min_age"] <= value <= cfg["max_age"]):
        return False, "AGE_OUT_OF_RANGE", None

    return True, None, value