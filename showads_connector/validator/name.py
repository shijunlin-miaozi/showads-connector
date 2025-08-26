import unicodedata
from showads_connector.types import NameValidationCode

def validate_name(name: object) -> tuple[bool, NameValidationCode | None, str | None]:
    """
    Validate that `name` contains letters (str.isalpha()) and single ASCII spaces (U+0020).
      - NFC normalize, strip ends
      - Reject any non-ASCII whitespace (tabs, NBSP, etc.)
      - Reject consecutive spaces
    Returns:
      (True, None, name_str)           on success
      (False, <reason_code>, None)     on failure
    """
    if not isinstance(name, str):
        return False, "NOT_A_STRING", None

    # normalize + strip
    s = unicodedata.normalize("NFC", name).strip() # NFC: Normalization Form C - Canonical Composition, e.g., ‘e’ + accent → ‘é’, making isalpha() check consistent
    if not s:
        return False, "EMPTY_AFTER_TRIM", None

    # single-pass scan for all rules
    last_was_space = False
    for ch in s:
        # reject any whitespace other than ASCII space
        if ch.isspace() and ch != " ":
            return False, "NON_ASCII_WHITESPACE", None

        # single space only between words (no consecutive spaces)
        if ch == " ":
            if last_was_space:           # "  " found
                return False, "DOUBLE_SPACE", None
            last_was_space = True
            continue

        # must be a letter
        if not ch.isalpha():
            return False, "NON_LETTER_CHAR", None
        
        last_was_space = False
        
    # all checks passed
    return True, None, s