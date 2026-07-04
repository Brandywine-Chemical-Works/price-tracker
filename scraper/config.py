"""
Central config for the scraper pipeline. Reads from environment variables
(populated by .env locally, or GitHub Actions Secrets in CI).
"""
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
ALERT_EMAIL_FROM = os.environ.get("ALERT_EMAIL_FROM", "alerts@brandywinechemicalworks.com")
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "brandywinechemicalworks@gmail.com")

PRICE_ALERT_THRESHOLD_PCT = float(os.environ.get("PRICE_ALERT_THRESHOLD_PCT", "5.0"))

REQUEST_TIMEOUT_SECONDS = 15
REQUEST_DELAY_SECONDS = 2.0  # politeness delay between scrape requests

# World Bank "Pink Sheet" commodity indicator codes used by worldbank.py.
# Add more here as the finance intern's chemical list grows.
WORLD_BANK_INDICATORS = {
    # World Bank doesn't track methanol directly; DAP (fertilizer) is used
    # here as a placeholder proxy so the pipeline is demonstrably working
    # end-to-end. Swap in real indicator codes as you find them (see
    # docs/SETUP.md for how to search the World Bank API catalog).
    "DAP (fertilizer, proxy)": "PFERT_WLD",
}


def validate_config() -> list[str]:
    """Return a list of missing required config values, empty if all present."""
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        missing.append("SUPABASE_SERVICE_KEY")
    if not SENDGRID_API_KEY:
        missing.append("SENDGRID_API_KEY (email alerts will be skipped)")
    return missing
