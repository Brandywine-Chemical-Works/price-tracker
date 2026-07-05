"""
World Bank Commodity Prices ("Pink Sheet") API.

Free, no API key required, returns JSON. Docs:
https://www.worldbank.org/en/research/commodity-markets
"""
from datetime import date
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from scraper import config
from scraper.logger_setup import get_logger

log = get_logger(__name__)

BASE_URL = "https://api.worldbank.org/v2/en/indicator/{code}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_indicator(indicator_code: str) -> list[dict]:
    url = BASE_URL.format(code=indicator_code)
    resp = requests.get(
        url,
        params={"format": "json", "per_page": 5, "mrnev": 1},
        timeout=config.REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": "BrandywinePriceTracker/1.0"},
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list) or len(data) < 2 or data[1] is None:
        raise ValueError(f"Unexpected World Bank API response shape for {indicator_code}")
    return data[1]


def fetch_price(chemical_name: str, indicator_code: str, unit: str) -> Optional[dict]:
    """Fetch the most recent price point for one indicator."""
    try:
        records = _fetch_indicator(indicator_code)
    except Exception as exc:
        log.error("worldbank_fetch_failed", extra={"chemical_name": chemical_name, "error": str(exc)})
        return None

    if not records:
        log.warning("worldbank_no_data", extra={"chemical_name": chemical_name})
        return None

    latest = records[0]
    if latest.get("value") is None:
        log.warning("worldbank_null_value", extra={"chemical_name": chemical_name})
        return None

    recorded = latest.get("date")
    try:
        date_recorded = date.fromisoformat(recorded) if recorded else date.today()
    except ValueError:
        date_recorded = date.today()

    return {
        "chemical_name": chemical_name,
        "price": float(latest["value"]),
        "unit": unit,
        "currency": "USD",
        "date_recorded": date_recorded,
        "source": "worldbank",
        "source_url": f"https://api.worldbank.org/v2/en/indicator/{indicator_code}?format=json",
    }


def fetch_all(chemical_names: Optional[list[str]] = None) -> list[dict]:
    """Fetch every chemical configured in config.WORLD_BANK_INDICATORS."""
    results = []
    for chemical_name, meta in config.WORLD_BANK_INDICATORS.items():
        if chemical_names is not None and chemical_name not in chemical_names:
            continue
        record = fetch_price(chemical_name, meta["code"], meta["unit"])
        if record:
            results.append(record)
    return results
