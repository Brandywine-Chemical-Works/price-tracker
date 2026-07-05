"""
Orchestrator entrypoint. Run with: python -m scraper.main

This is what the GitHub Actions workflow calls on a schedule. It:
  1. Reads active chemicals from Supabase config
  2. Pulls prices from each chemical's configured sources
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


def _chemicals_for_source(chemicals: list[dict], source: str) -> list[str]:
    return [
        c["chemical_name"]
        for c in chemicals
        if source in (c.get("sources") or [])
    ]


def run() -> int:
    missing = config.validate_config()
    if "SUPABASE_URL" in " ".join(missing) or "SUPABASE_SERVICE_KEY" in " ".join(missing):
        log.error("missing_required_config", extra={"missing": missing})
        return 1

    log.info("scrape_run_started")

    chemicals = db.get_active_chemicals()
    if not chemicals:
        log.warning("no_active_chemicals_in_config")

    chemanalyst_names = _chemicals_for_source(chemicals, "chemanalyst")
    worldbank_names = _chemicals_for_source(chemicals, "worldbank")

    failed_sources = []
    inserted_records = []

    # --- Source 1: ChemAnalyst (scraped HTML) ---
    if chemanalyst_names:
        try:
            chemanalyst_records = chemanalyst.fetch_all(chemical_names=chemanalyst_names)
            for record in chemanalyst_records:
                if db.insert_price(record):
                    inserted_records.append(record)
            if not chemanalyst_records:
                failed_sources.append("chemanalyst")
        except Exception as exc:
            log.error("chemanalyst_source_failed", extra={"error": str(exc)})
            failed_sources.append("chemanalyst")
    else:
        log.info("chemanalyst_skipped_no_configured_chemicals")

    # --- Source 2: World Bank (REST API) ---
    if worldbank_names:
        try:
            worldbank_records = worldbank.fetch_all(chemical_names=worldbank_names)
            for record in worldbank_records:
                if db.insert_price(record):
                    inserted_records.append(record)
            if not worldbank_records:
                failed_sources.append("worldbank")
        except Exception as exc:
            log.error("worldbank_source_failed", extra={"error": str(exc)})
            failed_sources.append("worldbank")
    else:
        log.info("worldbank_skipped_no_configured_chemicals")

    # --- Alert check on every newly inserted record ---
    alerts_fired = []
    chemicals_config = {c["chemical_name"]: c for c in chemicals}
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

    active_sources = int(bool(chemanalyst_names)) + int(bool(worldbank_names))
    if active_sources == 0:
        return 1
    return 1 if len(failed_sources) >= active_sources else 0


if __name__ == "__main__":
    sys.exit(run())
