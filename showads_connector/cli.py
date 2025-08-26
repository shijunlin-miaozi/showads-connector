import argparse
import logging
import sys
from dotenv import load_dotenv

from showads_connector.config import Config
from showads_connector.showads.auth import AuthClient
from showads_connector.showads.client import ShowAdsClient
from showads_connector import pipeline

load_dotenv()  # loads .env into process env

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="showads-connector",
        description="Load a CSV, validate rows, and send to ShowAds.",
    )
    p.add_argument("csv", help="Path to input CSV (data.csv)")

    # Live-reload config file (ages)
    p.add_argument(
        "--config-file",
        default=None,
        help='Path to JSON config for live-reload (e.g., {"min_age": 18, "max_age": 120})',
    )
    p.add_argument("--min-age", type=int, default=None, help="Override minimum age (CLI has highest precedence)")
    p.add_argument("--max-age", type=int, default=None, help="Override maximum age (CLI has highest precedence)")
    p.add_argument(
        "--reload-interval-s",
        type=float,
        default=5.0,
        help="How often to poll the config file for changes (seconds)",
    )
    p.add_argument(
        "--reload-every-rows",
        type=int,
        default=10_000,
        help="Check for config reload every N processed rows",
    )

    # Pipeline
    p.add_argument("--batch-size", type=int, default=1000, help="Bulk API limit (spec: 1000)")
    p.add_argument("--log-every-rows", type=int, default=10_000, help="Progress log cadence")

    # Base URL / Project Key (CLI overrides; if omitted, config/env/defaults apply)
    p.add_argument("--base-url", default=None, help="Override ShowAds base URL")
    p.add_argument("--project-key", default=None, help="Override ProjectKey for /auth")

    # HTTP (ShowAdsClient)
    p.add_argument("--timeout-connect", type=float, default=3.0, help="Connect timeout (seconds)")
    p.add_argument("--timeout-read-single", type=float, default=10.0, help="Read timeout for single requests")
    p.add_argument("--timeout-read-bulk", type=float, default=15.0, help="Read timeout for bulk requests")
    p.add_argument("--max-retries", type=int, default=3, help="Max retries for 429/5xx/transport errors")
    p.add_argument("--backoff-base-s", type=float, default=0.5, help="Exponential backoff base (seconds)")
    p.add_argument("--backoff-cap-s", type=float, default=8.0, help="Exponential backoff cap (seconds)")

    # Logging
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # --- logging setup ---
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("cli")

    # --- build config (live-reload for age only; base_url/project_key loaded once) ---
    # Precedence: CLI > file > env > defaults
    cfg = Config(
        file_path=args.config_file,
        min_age=args.min_age,
        max_age=args.max_age,
        base_url=args.base_url,
        project_key=args.project_key,
        check_interval_s=args.reload_interval_s,
    )

    # Warn early if project key is empty (the API will 400 on /auth)
    if not cfg.project_key():
        logger.warning("PROJECT_KEY is empty; /auth will likely respond 400 (Bad Request).")

    # --- auth + client ---
    auth = AuthClient(
        base_url=cfg.base_url(),
        project_key=cfg.project_key(),
        # session=..., proactive_refresh_seconds=... (use defaults for now)
    )

    client = ShowAdsClient(
        base_url=cfg.base_url(),
        auth=auth,
        timeout_single=(args.timeout_connect, args.timeout_read_single),
        timeout_bulk=(args.timeout_connect, args.timeout_read_bulk),
        max_batch=args.batch_size,
        max_retries=args.max_retries,
        backoff_base_s=args.backoff_base_s,
        backoff_cap_s=args.backoff_cap_s,
    )

    # --- run pipeline ---
    try:
        summary = pipeline.run_pipeline(
            csv_path=args.csv,
            cfg=cfg,
            client=client,
            batch_size=args.batch_size,
            reload_every_rows=args.reload_every_rows,
            log_every_rows=args.log_every_rows,
        )
        logger.info("Summary: %s", summary)
        # Exit non-zero if we had valid items we couldn't send at all
        exit_code = 1 if summary.get("unsent_valid", 0) > 0 else 0
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(2)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
