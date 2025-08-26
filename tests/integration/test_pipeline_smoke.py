# Pipeline “smoke” test: end-to-end without real HTTP.
# Uses a fake ShowAdsClient, so it checks CSV → validation → batching → summary,
# It’s not a true integration against the live API.

import json
import os
import time

from showads_connector.pipeline import run_pipeline
from showads_connector.config import Config


class FakeShowAdsClient:    # minimal stand-in for the real HTTP client
    def __init__(self):
        self._max_batch = 1000  # match spec/client cap
        self.calls = []         # record what was sent

    def send_bulk(self, items):
        # pretend all items succeed
        self.calls.append(list(items))
        return {"sent": len(items), "failed": []}

def _write_csv(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8", newline="\n")
    return str(p)

def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    # bump mtime so Config sees a change
    os.utime(path, None)    # updates the file’s timestamps; None: set access time (atime) and modification time (mtime) to now

def test_pipeline_tiny_csv_happy_path(tmp_path):
    """
    Tiny CSV: 2 valid rows + 1 invalid age -> summary counts match.
    """
    csv_path = _write_csv(
        tmp_path,
        "tiny.csv",
        # Header + 3 rows. Ages: 30 (valid), "abc" (invalid), 19 (valid).
        "Name,Age,Cookie,Banner_id\n"
        "John,30,550e8400-e29b-41d4-a716-446655440000,1\n"
        "Jane,abc,550e8400-e29b-41d4-a716-446655440000,2\n"
        "Ana,19,550e8400-e29b-41d4-a716-446655440000,3\n"
    )

    # Default Config (min=18, max=120); no file reload used here
    cfg = Config(file_path=None, check_interval_s=0.0)

    client = FakeShowAdsClient()
    summary = run_pipeline(
        csv_path=csv_path,
        cfg=cfg,
        client=client,
        batch_size=1000,
        reload_every_rows=1000,
        log_every_rows=10_000,
    )

    # processed = 3 total rows
    assert summary["processed"] == 3
    # valid = 2 (ages 30 and 19), invalid = 1 ("abc")
    assert summary["valid"] == 2
    assert summary["invalid"] == 1
    # API accepted both valid -> sent=2, failed=0
    assert summary["sent"] == 2
    assert summary["failed"] == 0
    # No fatal send errors
    assert summary["unsent_valid"] == 0
    # Age error counted
    assert summary["invalid_reasons"].get("NOT_AN_INTEGER", 0) == 1

def test_pipeline_reload_changes_age_bounds(tmp_path, monkeypatch):
    """
    Live-reload case: start with min_age=18, then raise to min_age=50
    between rows, causing the second row (Age=30) to become invalid.
    """
    # Make a real config file so Config can reload it
    cfg_path = tmp_path / "config.json"
    _write_json(cfg_path, {"min_age": 18, "max_age": 120})

    # Build Config with zero polling interval so every check can reload
    cfg = Config(file_path=str(cfg_path), check_interval_s=0.0)

    # monkeypatch iter_csv_rows used by pipeline to insert a file update
    from showads_connector import pipeline as pl

    rows = [
        (2, {"Name": "One", "Age": "25", "Cookie": "550e8400-e29b-41d4-a716-446655440000", "Banner_id": "1"}),  # valid under both
        (3, {"Name": "Two", "Age": "30", "Cookie": "550e8400-e29b-41d4-a716-446655440000", "Banner_id": "2"}),  # will become invalid after min_age=50
        (4, {"Name": "Three", "Age": "60", "Cookie": "550e8400-e29b-41d4-a716-446655440000", "Banner_id": "3"}),# valid under new bounds
    ]

    def fake_iter_csv_rows(_path):
        yield rows[0]   # yield first row (min_age=18)
        _write_json(cfg_path, {"min_age": 50, "max_age": 120})  # now raise min_age to 50 and bump mtime
        # Force a different mtime (add >=1s to be safe on coarse filesystems)
        now = time.time()
        os.utime(cfg_path, (now + 2, now + 2))
        # yield the rest
        yield rows[1]   # now 30 is out of range
        yield rows[2]   # 60 still valid

    monkeypatch.setattr(pl, "iter_csv_rows", fake_iter_csv_rows)    # replace the real CSV iterator with fake one

    client = FakeShowAdsClient()
    summary = pl.run_pipeline(
        csv_path="ignored.csv",          # our fake_iter_csv_rows ignores this
        cfg=cfg,
        client=client,
        batch_size=1000,
        reload_every_rows=1,             # check reload on every row
        log_every_rows=10_000,
    )

    # processed=3 total rows
    assert summary["processed"] == 3
    # After raising min_age to 50, second row (Age=30) should be invalid.
    # valid rows: first (25) before change, third (60) after change => 2 valid, 1 invalid
    assert summary["valid"] == 2
    assert summary["invalid"] == 1
    # Both valid rows were sent
    assert summary["sent"] == 2
    assert summary["failed"] == 0
    assert summary["unsent_valid"] == 0
    # The invalid reason should be AGE_OUT_OF_RANGE for the 30-year-old row
    assert summary["invalid_reasons"].get("AGE_OUT_OF_RANGE", 0) == 1
