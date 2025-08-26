import json
import logging
import os
import time

from showads_connector.types import AgeConfig

logger = logging.getLogger(__name__)

# Defaults and env var names
DEFAULT_MIN_AGE = 18
DEFAULT_MAX_AGE = 120
ENV_MIN = "MIN_AGE"
ENV_MAX = "MAX_AGE"

# Assignment-specific base URL (used if env/CLI not provided)
DEFAULT_BASE_URL = "https://golang-assignment-968918017632.europe-west3.run.app"
ENV_BASE_URL = "BASE_URL"
ENV_PROJECT_KEY = "PROJECT_KEY"


# ---------- helper functions ----------

def _env_int(name: str, default: int) -> int:
    """Read an int from the environment; return default if missing or invalid."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except Exception:
        logger.warning("Invalid int in env %s=%r (using default=%s)", name, raw, default)
        return default


def _load_json_file(path: str) -> dict:
    """
    Read a small JSON file. If the file is missing or invalid,
    return {} and log a message.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.info("Config file not found: %s (keeping current settings)", path)
    except Exception as e:
        logger.warning("Could not read config file %s: %s (keeping current settings)", path, e)
    return {}


def _validate_age_bounds(min_age: int, max_age: int) -> None:
    """Make sure the age limits make sense."""
    if min_age > max_age:
        raise ValueError(f"min_age({min_age}) > max_age({max_age})")
    if min_age < 0 or max_age < 0:
        raise ValueError(f"Age bounds must be non-negative (got {min_age}..{max_age})")


def _get_mtime(path: str | None) -> float | None:
    """Return the file's last modification time, or None if not available."""
    if not path:
        return None
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


# ---------- live-reload config ----------

class Config:
    """
    Small runtime config holder with **polling-based reload**.
    What it does:
      - Keeps min/max age in memory.
      - Every few seconds (or whenever you call reload_if_needed()), it checks if the
        config file on disk changed. If yes, it re-reads values.
      - Precedence when loading: CLI overrides > file > env vars > defaults.
    How to use:
      cfg = Config(file_path="config.json", min_age=args.min_age, max_age=args.max_age, check_interval_s=5)
      ...
      if cfg.reload_if_needed():
          age_cfg = cfg.age()   # {'min_age': int, 'max_age': int}
    Notes:
      - Update the file with an **atomic replace**: write to a temp file and then os.replace()
        to avoid partial reads.
      - This class assumes a single-threaded pipeline. If you add threads later, you may
        want to add a lock around reads/writes.
        
    BASE_URL and PROJECT_KEY are loaded once at startup (no live reload)
    """

    def __init__(
        self,
        *,
        file_path: str | None = None,
        min_age: int | None = None,
        max_age: int | None = None,
        base_url: str | None = None,
        project_key: str | None = None,
        check_interval_s: float = 5.0,
    ) -> None:
        # --- static settings (loaded once; simple env/CLI) ---
        self._base_url = (base_url or os.getenv(ENV_BASE_URL) or DEFAULT_BASE_URL).strip().rstrip("/")
        self._project_key = (project_key or os.getenv(ENV_PROJECT_KEY) or "").strip()
        # Note: spec says any ProjectKey works; if empty, /auth will return 400. We leave it as-is.
        
        # --- live-reload for age bounds ---
        self._file_path = file_path
        self._file_mtime: float | None = _get_mtime(file_path)

        # Remember CLI overrides so they always win on reload
        self._cli_min = min_age
        self._cli_max = max_age

        # Only check the filesystem this often; cheap to call reload_if_needed() more often
        self._interval = max(0.0, float(check_interval_s))
        self._next_check = time.monotonic()  # first call will perform a check

        # Current effective values (start with defaults, then load once)
        self._age: AgeConfig = {"min_age": DEFAULT_MIN_AGE, "max_age": DEFAULT_MAX_AGE}
        self._reload_from_sources(initial=True)

    # ----- public API -----

    def base_url(self) -> str:
        """Assignment API base URL (static)."""
        return self._base_url

    def project_key(self) -> str:
        """Project key for /auth (static)."""
        return self._project_key

    def age(self) -> AgeConfig:
        """Return a copy of the current min/max age."""
        return dict(self._age)

    def reload_if_needed(self) -> bool:
        """
        Check the file's modification time at most once per `check_interval_s`.
        If the file changed, reload values and return True. Otherwise return False.
        """
        now = time.monotonic()
        if now < self._next_check:
            return False
        self._next_check = now + self._interval

        new_mtime = _get_mtime(self._file_path)
        if new_mtime == self._file_mtime:
            return False  # no change

        # mtime changed: try to reload. Record mtime first to avoid repeated work on errors.
        old_mtime = self._file_mtime
        self._file_mtime = new_mtime

        old_age = dict(self._age)
        self._reload_from_sources(initial=False)

        if self._age != old_age:
            logger.info("Age config changed: %s -> %s (mtime %s -> %s)", old_age, self._age, old_mtime, new_mtime)
            return True

        # File changed but values stayed the same (e.g., re-wrote same content)
        logger.debug("Config file changed but age values are the same: %s", self._age)
        return False

    # ----- internal helpers -----

    def _reload_from_sources(self, *, initial: bool) -> None:
        """
        Build new min/max from:
          1) defaults
          2) env vars (MIN_AGE, MAX_AGE)
          3) file (if provided)
          4) CLI overrides (always win)
        Validate and then apply. On startup, invalid values raise. On reload, keep the
        previous good values and log a warning.
        """
        min_age = DEFAULT_MIN_AGE
        max_age = DEFAULT_MAX_AGE

        # env
        min_age = _env_int(ENV_MIN, min_age)
        max_age = _env_int(ENV_MAX, max_age)

        # file
        if self._file_path:
            data = _load_json_file(self._file_path)
            if isinstance(data.get("min_age"), int):
                min_age = data["min_age"]
            if isinstance(data.get("max_age"), int):
                max_age = data["max_age"]

        # cli overrides
        if self._cli_min is not None:
            min_age = self._cli_min
        if self._cli_max is not None:
            max_age = self._cli_max

        # validate and apply
        try:
            _validate_age_bounds(min_age, max_age)
        except ValueError as e:
            if initial:
                # On startup, bad config should stop the program.
                raise
            logger.warning("Invalid age bounds on reload (%s). Keeping previous: %s", e, self._age)
            return

        self._age = {"min_age": min_age, "max_age": max_age}
