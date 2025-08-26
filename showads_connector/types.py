from typing import Literal, TypedDict

# --- name-specific reason codes ---
NameValidationCode = Literal[
    "NOT_A_STRING",
    "EMPTY_AFTER_TRIM",
    "NON_ASCII_WHITESPACE",
    "DOUBLE_SPACE",
    "NON_LETTER_CHAR",
]

# --- cookie-specific reason codes ---
CookieValidationCode = Literal[
    "NOT_A_STRING",
    "EMPTY_AFTER_TRIM",
    "BAD_UUID",
    "NIL_UUID"
]

# --- banner_id-specific reason codes ---
BannerIDValidationCode = Literal[
    "NOT_AN_INTEGER",
    "EMPTY_AFTER_TRIM",
    "ID_OUT_OF_RANGE",
]

# --- age-specific reason codes ---
AgeValidationCode = Literal[
    "NOT_AN_INTEGER",
    "EMPTY_AFTER_TRIM",
    "AGE_OUT_OF_RANGE",
]

class AgeConfig(TypedDict):
    min_age: int
    max_age: int
    
class BatchResult(TypedDict):
    sent: int
    failed: list[dict[str, object]]  # return {"item": {...}, "reason": str, "status": int | None}
