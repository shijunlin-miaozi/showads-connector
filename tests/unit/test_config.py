import json
import os
from showads_connector.config import Config

def _write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")     # write a Python dict as JSON to path

def _bump_mtime(path):
    # forces mtime to move forward
    m = os.path.getmtime(path)
    os.utime(path, (m, m + 2))

def test_precedence_defaults_env_file_cli(tmp_path, monkeypatch):   # tmp_path: temp directory; monkeypatch: tweak env vars
    # Start clean
    monkeypatch.delenv("MIN_AGE", raising=False)
    monkeypatch.delenv("MAX_AGE", raising=False)

    # defaults
    cfg = Config(check_interval_s=0)
    assert cfg.age() == {"min_age": 18, "max_age": 120}

    # env overrides defaults
    monkeypatch.setenv("MIN_AGE", "30")
    monkeypatch.setenv("MAX_AGE", "40")
    cfg = Config(check_interval_s=0)
    assert cfg.age() == {"min_age": 30, "max_age": 40}

    # file overrides env
    p = tmp_path / "config.json"
    _write_json(p, {"min_age": 25, "max_age": 35})
    cfg = Config(file_path=str(p), check_interval_s=0)
    assert cfg.age() == {"min_age": 25, "max_age": 35}

    # CLI overrides file/env
    cfg = Config(file_path=str(p), min_age=50, max_age=60, check_interval_s=0)
    assert cfg.age() == {"min_age": 50, "max_age": 60}

def test_reload_if_needed_valid_then_invalid(tmp_path, caplog):
    # start with a valid file and confirm values are loaded
    p = tmp_path / "config.json"
    _write_json(p, {"min_age": 20, "max_age": 30})
    cfg = Config(file_path=str(p), check_interval_s=0)  # check_interval_s=0 makes reload checks immediate
    assert cfg.age() == {"min_age": 20, "max_age": 30}

    # Change to valid values → applies
    _write_json(p, {"min_age": 21, "max_age": 31})
    _bump_mtime(str(p))
    assert cfg.reload_if_needed() is True
    assert cfg.age() == {"min_age": 21, "max_age": 31}

    # Change to invalid values → rejected, previous kept
    _write_json(p, {"min_age": 40, "max_age": 30})  # min > max
    _bump_mtime(str(p))
    changed = cfg.reload_if_needed()
    assert changed is False
    assert cfg.age() == {"min_age": 21, "max_age": 31}
