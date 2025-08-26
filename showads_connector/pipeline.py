import logging
import time
from collections import Counter
from typing import Any

from .config import Config
from .csv_reader import iter_csv_rows
from .validator.name import validate_name
from .validator.age import validate_age
from .validator.cookie import validate_cookie
from .validator.banner import validate_banner_id
from .showads.client import ShowAdsClient
from .showads import errors as err

logger = logging.getLogger(__name__)


def run_pipeline(
    csv_path: str,
    cfg: Config,
    client: ShowAdsClient,
    *,
    batch_size: int = 1000,         # API limit per spec
    reload_every_rows: int = 10_000, # how often to check live-reload
    log_every_rows: int = 10_000     # periodic progress log
) -> dict[str, Any]:
    """
    Stream the CSV, validate, batch, and send to ShowAds.

    Returns a summary dict:
      {
        "processed": int,           # total rows read from CSV (including invalid)
        "valid": int,               # rows that passed validation
        "invalid": int,             # rows that failed validation
        "sent": int,                # valid items accepted by API
        "failed": int,              # valid items that failed even after retries/fallback
        "unsent_valid": int,        # valid items we could not send due to fatal errors
        "invalid_reasons": {code: count, ...},
        "duration_s": float
      }

    Notes:
    - We never store the whole file in memory; batches are sent as they fill.
    - Age limits come from Config (which supports polling-based live reload).
    - All HTTP/resilience lives in ShowAdsClient.
    """
    
    # Cap requested batch size at the client/API limit.
    # Warn if we had to cap so it’s visible in logs.
    desired = batch_size
    cap = getattr(client, "_max_batch", desired)
    effective_batch = min(desired, cap)
    if effective_batch != desired:
        logger.warning(
            "Requested batch_size=%d exceeds client cap=%d; capping to %d.",
            desired, cap, effective_batch
        )
    
    t0 = time.time()

    processed = 0
    valid = 0
    invalid = 0
    sent = 0
    failed = 0
    unsent_valid = 0
    reason_counts: Counter[str] = Counter()

    batch: list[dict[str, object]] = []   # each item: {"VisitorCookie": str, "BannerId": int}

    def flush_batch() -> None:
        nonlocal sent, failed, unsent_valid, batch  # nonlocal allows clean update of the outer counters
        if not batch:
            return
        try:
            result = client.send_bulk(batch)
            sent += result["sent"]
            failed += len(result["failed"])
        except err.ShowAdsError as e:
            # Unrecoverable for this batch (e.g., Unauthorized after refresh, or retries exhausted)
            logger.error(
                "Batch send failed: type=%s status=%s endpoint=%s msg=%s size=%d",
                e.__class__.__name__, getattr(e, "status", None), getattr(e, "endpoint", None), str(e), len(batch)
            )
            unsent_valid += len(batch)
        finally: # ensures the buffer is cleared in all cases
            batch.clear()

    # Get the initial age limits once before processing rows
    age_cfg = cfg.age()

    for line_index, row in iter_csv_rows(csv_path):
        processed += 1

        # Periodic config reload and progress logs
        if processed % reload_every_rows == 0:
            if cfg.reload_if_needed():
                age_cfg = cfg.age()
        if processed % log_every_rows == 0:
            logger.info("Progress: processed=%d valid=%d invalid=%d sent=%d failed=%d",
                        processed, valid, invalid, sent, failed)

        # Extract raw fields (header was validated by csv_reader, so keys exist)
        name_raw = row.get("Name", "")
        age_raw = row.get("Age", "")
        cookie_raw = row.get("Cookie", "")
        banner_raw = row.get("Banner_id", "")

        # Check fields one by one; if any check fails, log why and skip this row
        ok, code, name_val = validate_name(name_raw)
        if not ok:
            invalid += 1
            reason_counts[str(code)] += 1
            logger.debug("Invalid row (line=%d) reason=%s field=Name value=%r", line_index, code, name_raw)
            continue

        ok, code, age_val = validate_age(age_raw, age_cfg)
        if not ok:
            invalid += 1
            reason_counts[str(code)] += 1
            logger.debug("Invalid row (line=%d) reason=%s field=Age value=%r", line_index, code, age_raw)
            continue

        ok, code, cookie_val = validate_cookie(cookie_raw)
        if not ok:
            invalid += 1
            reason_counts[str(code)] += 1
            logger.debug("Invalid row (line=%d) reason=%s field=Cookie value=%r", line_index, code, cookie_raw)
            continue

        ok, code, banner_val = validate_banner_id(banner_raw)
        if not ok:
            invalid += 1
            reason_counts[str(code)] += 1
            logger.debug("Invalid row (line=%d) reason=%s field=Banner_id value=%r", line_index, code, banner_raw)
            continue

        # Passed all validation rules -> build ShowAds payload item
        valid += 1
        batch.append({"VisitorCookie": cookie_val, "BannerId": banner_val})

        # When batch is full, send it
        if len(batch) >= effective_batch:
            flush_batch()

    # Send any leftover items
    flush_batch()

    summary = {
        "processed": processed,
        "valid": valid,
        "invalid": invalid,
        "sent": sent,
        "failed": failed,
        "unsent_valid": unsent_valid,
        "invalid_reasons": dict(reason_counts),
        "duration_s": round(time.time() - t0, 3),
    }

    logger.debug("Final summary: %s", summary)
    return summary