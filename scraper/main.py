"""
Orchestrator entrypoint. Run with: python -m scraper.main

This is what the GitHub Actions workflow calls on a schedule. It:
  1. Reads active chemicals from Supabase config
  2. Pulls prices from every configured source
  3. Normalizes + inserts into Supabase (idempotent - safe to re-run)
  4. Checks each new price against its 7-day rolling average, alerts if needed
  5. Sends a daily health-check email summarizing the run
"""
import sys

from scraper import config, db
from scraper.alerts import check_and_alert, send_health_check
from scraper.logger_setup import get_logger
from scraper.sources import chemanalyst, worldbank

log = get_logger(__name__)


def run() -> int:
    missing = config.validate_config()
    if "SUPABASE_URL" in " ".join(missing) or "SUPABASE_SERVICE_KEY" in " ".join(missing):
        log.error("missing_required_config", extra={"missing": missing})
        return 1

    log.info("scrape_run_started")

    failed_sources = []
    inserted_records = []

    # --- Source 1: ChemAnalyst (scraped HTML) ---
    try:
        chemanalyst_records = chemanalyst.fetch_all()
        for record in chemanalyst_records:
            if db.insert_price(record):
                inserted_records.append(record)
    except Exception as exc:
        log.error("chemanalyst_source_failed", extra={"error": str(exc)})
        failed_sources.append("chemanalyst")

    # --- Source 2: World Bank (REST API) ---
    try:
        worldbank_records = worldbank.fetch_all()
        for record in worldbank_records:
            if db.insert_price(record):
                inserted_records.append(record)
    except Exception as exc:
        log.error("worldbank_source_failed", extra={"error": str(exc)})
        failed_sources.append("worldbank")

    # --- Alert check on every newly inserted record ---
    alerts_fired = []
    chemicals_config = {c["chemical_name"]: c for c in db.get_active_chemicals()}
    for record in inserted_records:
        cfg = chemicals_config.get(record["chemical_name"])
        threshold = cfg["alert_threshold_pct"] if cfg else config.PRICE_ALERT_THRESHOLD_PCT
        alert = check_and_alert(record["chemical_name"], record["price"], threshold)
        if alert:
            alerts_fired.append(alert)

    send_health_check(len(inserted_records), failed_sources, alerts_fired)

    log.info(
        "scrape_run_finished",
        extra={
            "inserted": len(inserted_records),
            "failed_sources": failed_sources,
            "alerts_fired": len(alerts_fired),
        },
    )

    # Non-zero exit if every source failed, so GitHub Actions flags the run red.
    return 1 if len(failed_sources) == 2 else 0


if __name__ == "__main__":
    sys.exit(run())
