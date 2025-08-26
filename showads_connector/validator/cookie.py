import uuid
from showads_connector.types import CookieValidationCode

def validate_cookie(cookie: object) -> tuple[bool, CookieValidationCode | None, str | None]:
    """
    Validate that `cookie` is a non-empty string in UUID format.
    - Must be str
    - Trimmed; empty after trim is invalid
    - Parsed via uuid.UUID(); accepts hyphenated/32-hex/braced/URN
    - Rejects the nil UUID
    Returns:
      (True, None, canonical_uuid)    on success
      (False, <reason_code>, None)    on failure
    """
    if not isinstance(cookie, str):
        return False, "NOT_A_STRING", None
    
    s = cookie.strip()
    if not s:
        return False, "EMPTY_AFTER_TRIM", None
    
    # parse any standard textual form
    try:
        u = uuid.UUID(s)
    except ValueError:
        return False, "BAD_UUID", None
    
    if u.int == 0:
        return False, "NIL_UUID", None

    return True, None, str(u)    # return canonical lowercase-hyphenated UUID text