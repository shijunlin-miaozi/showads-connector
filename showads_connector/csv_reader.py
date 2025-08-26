import csv
import logging
from collections.abc import Iterator

logger = logging.getLogger(__name__)


# expected schema per spec. fail fast if headers don’t match.
_EXPECTED_HEADERS = frozenset({"Name", "Age", "Cookie", "Banner_id"})

def iter_csv_rows(path: str, *, encoding: str = "utf-8-sig") -> Iterator[tuple[int, dict[str, str]]]:
    """
    stream rows from a CSV file as dicts keyed by header names.
    - uses utf-8-sig to tolerate BOM.
    - yields (line_index, row_dict) one at a time (low memory).
    - performs only neutral normalization (no business validation).
    """
    with open(path, "r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(
            f,
            skipinitialspace=True,  # ignore spaces right after delimiter, e.g., ", Age"
            restval="",             # missing cells (fewer cells than headers) -> ""
        )
        # ---- header checks ----
        fieldnames = reader.fieldnames
        if fieldnames is None:
            logger.error("CSV %s: no header row found", path)
            raise ValueError("CSV has no header row.")
        
        raw_headers: list[str] = fieldnames
        trimmed_headers = [(h or "").strip() for h in raw_headers]
        
        # detect duplicates after trimming
        if len(set(trimmed_headers)) != len(trimmed_headers):
            dupes = [h for h in set(trimmed_headers) if trimmed_headers.count(h) > 1]
            logger.error(
                "CSV %s: duplicate headers after trimming: %s (raw headers: %s)",
                path, dupes, raw_headers
            )
            raise ValueError(f"Duplicate headers after trimming: {dupes}")
        
        # Missing required headers
        missing = [h for h in _EXPECTED_HEADERS if h not in trimmed_headers]
        if missing:
            logger.error(
                "CSV %s: missing required headers: %s (found: %s)",
                path, missing, trimmed_headers
            )
            raise ValueError(f"Missing required headers: {missing} (found: {trimmed_headers})")
        
        # Unknown headers (not fatal -> ignored by design)
        unknown = [h for h in trimmed_headers if h not in _EXPECTED_HEADERS]
        if unknown:
            logger.warning("CSV %s: ignoring unknown headers: %s", path, unknown)
        
        # map raw header -> trimmed header (apply once, reuse per row)
        rename = {raw: trimmed for raw, trimmed in zip(raw_headers, trimmed_headers)}
        
        # ---- rows ----
        for line_index, raw in enumerate(reader, start=2):  # header is line 1
            # build a trimmed dict with canonical (trimmed) keys
            row: dict[str, str] = {}
            for raw_key, val in raw.items():
                if raw_key is None:
                    continue
                key = rename[raw_key]
                if key in _EXPECTED_HEADERS:  # ignore unknowns cleanly
                    row[key] = (val or "").strip()
                    
            # skip blank/empty lines (all expected fields empty)
            if not row or not any(row.values()):
                continue
            
            yield line_index, row
