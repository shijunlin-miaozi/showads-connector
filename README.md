# showads-connector

CSV → validate → batch → send to ShowAds API.  
Includes live-reloadable age limits, robust HTTP client with retries/backoff, and a simple CLI.

---

## Quick Start (Local)

### 1) Optional: create & activate a venv
```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Prepare config (optional but recommended)
`config.json`:
```json
{ "min_age": 18, "max_age": 120 }
```

Environment variables (either export these or pass flags later):
```
PROJECT_KEY=your_project_key
BASE_URL=https://golang-assignment-968918017632.europe-west3.run.app
```

### 4) Run the connector
```bash
python -m showads_connector   path/to/data.csv   --config-file ./config.json   --project-key "$PROJECT_KEY"   --base-url "$BASE_URL"   --log-level INFO
```

> Notes:
> - CLI flags override config file and env vars.
> - Required CSV headers: `Name, Age, Cookie, Banner_id`. Unknown headers are ignored.

---

## Quick Start (Docker)

### 1) Build the image
```bash
docker build -t showads-connector:latest .
```

### 2) Run with a mounted CSV and config
```bash
docker run --rm -it   --env PROJECT_KEY=your_project_key   --env BASE_URL=https://golang-assignment-968918017632.europe-west3.run.app   -v "$PWD/example_data_small.csv:/data/data.csv:ro"   -v "$PWD/config.json:/config/config.json:ro"   showads-connector:latest   /data/data.csv --config-file /config/config.json --log-level INFO
```

Or load envs from a file:
```bash
# .env
# PROJECT_KEY=your_project_key
# BASE_URL=https://golang-assignment-968918017632.europe-west3.run.app
# MIN_AGE=18
# MAX_AGE=120

docker run --rm -it   --env-file .env   -v "$PWD/example_data_small.csv:/data/data.csv:ro"   -v "$PWD/config.json:/config/config.json:ro"   showads-connector:latest   /data/data.csv --config-file /config/config.json --log-level INFO
```

> The container runs the job and exits (it won’t show as a long-running container).

---

## CSV Format

Required headers: `Name, Age, Cookie, Banner_id`  
Unknown headers are ignored.

Example:
```csv
Name,Age,Cookie,Banner_id
John Doe,35,26555324-53df-4eb1-8835-e6c0078bb2c0,12
```

---

## Config & Precedence

- Live-reload file (`--config-file`):
  ```json
  { "min_age": 18, "max_age": 120 }
  ```
- Env vars: `PROJECT_KEY`, `BASE_URL`, `MIN_AGE`, `MAX_AGE`
- **Precedence:** defaults < env < config file < CLI flags.

---

## Useful CLI Flags

- Connection: `--project-key`, `--base-url`
- Validation: `--min-age`, `--max-age`, `--config-file`
- Batching: `--batch-size` (default 1000), `--reload-every-rows`, `--log-every-rows`
- Timeouts/retries: `--timeout-connect`, `--timeout-read-single`, `--timeout-read-bulk`, `--max-retries`, `--backoff-base-s`, `--backoff-cap-s`
- Logging: `--log-level {DEBUG,INFO,WARNING,ERROR}`

---

## Testing

Local:
```bash
pytest -q
```

In Docker (bind-mount your workspace and run tests inside):
```bash
docker run --rm -it \
  -v "$PWD:/app" -w /app \
  --entrypoint bash \
  showads-connector:latest -lc "python -m pip install -r requirements.txt && PYTHONPATH=/app pytest -q"
```

### pytest run variations
- Run all tests:
```bash
pytest
```
- Run only certain tests folder:
```bash
pytest tests/unit
pytest tests/integration
```
- Run single file:
```bash
pytest tests/unit/validator/test_name.py
```
- Run single test function:
```bash
pytest tests/unit/validator/test_name.py::test_ok_basic
```
- Verbose output:
```bash
pytest -vv
```
---

## Design Overview

**Goal**  
Stream CSV → validate → batch → send to ShowAds; be robust (retries, auth refresh), observable (logs), and simple to operate.

**Key Modules**
- `csv_reader.py` — streams rows, trims, validates headers.
- `validator/*` — validators (name/age/cookie/banner).
- `config.py` — age bounds with polling-based live reload.
- `showads/auth.py` — caches `/auth` token, pre-refreshes near TTL.
- `showads/client.py` — `_post_with_retry` (401 refresh-once; 429/5xx/transport retries with backoff); `send_single` & `send_bulk` with fallback.
- `pipeline.py` — wiring: validate → batch → send; periodic reload & progress logs.
- `cli.py` — argparse entrypoint.

**Data Flow**
CSV row → validate → enqueue → when full call `send_bulk()` → if bulk 400, fall back to per-item.

**Errors & Retries**
Typed exceptions in `errors.py`. 401 → one refresh attempt. 429/5xx/transport → exponential backoff (honors `Retry-After`) up to `max_retries`. 400 → not retried.

**Config Precedence**
Defaults < env < file < CLI. Only age bounds live-reload.

**Logging**
INFO summaries/progress, WARNING for fallbacks/retries, DEBUG for details.

**Testing**
Unit tests for validators, config reload, error mapping, retry logic. “Smoke” tests with stubbed HTTP.

**Limits & Choices**
Batch size capped at API spec (1000). Uses `requests.Session`. Dependency-light.
