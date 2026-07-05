"""
ChemAnalyst price page scraper (static HTML + BeautifulSoup).

Fetches regional price cards from ChemAnalyst product pages and prefers the
USA spot price (USD/MT), falling back to the first USD/MT value on the page.
"""
import re
import time
from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

from scraper import config
from scraper.logger_setup import get_logger

log = get_logger(__name__)

_ua = UserAgent()

# Verified live ChemAnalyst pricing pages (each is an independent price source).
CHEMANALYST_TARGETS = {
    "Methanol": "https://www.chemanalyst.com/Pricing-data/methanol-1",
    "Formaldehyde": "https://www.chemanalyst.com/Pricing-data/formaldehyde-1214",
    "Biodiesel": "https://www.chemanalyst.com/Pricing-data/biodiesel-77",
    "Natural Gas": "https://www.chemanalyst.com/Pricing-data/natural-gas-1339",
    "Palm Oil": "https://www.chemanalyst.com/Pricing-data/palm-oil-1319",
    "MTBE": "https://www.chemanalyst.com/Pricing-data/methyl-tertiary-butyl-ether-81",
    "Used Cooking Oil": "https://www.chemanalyst.com/Pricing-data/used-cooking-oil-uco-2322",
    "Coal": "https://www.chemanalyst.com/Pricing-data/coal-1522",
}

_USA_PRICE_RE = re.compile(
    r"(?:in|for)\s+USA[^.]{0,60}?USD\s*([\d,]+\.?\d*)\s*/\s*MT",
    re.IGNORECASE,
)
_ANY_PRICE_RE = re.compile(r"USD\s*([\d,]+\.?\d*)\s*/\s*MT", re.IGNORECASE)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_html(url: str) -> str:
    headers = {"User-Agent": _ua.random}
    resp = requests.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    if "/Pricing-data/" not in resp.url:
        raise ValueError(f"ChemAnalyst redirected away from pricing page: {resp.url}")
    return resp.text


def _parse_price_table(html: str) -> Optional[dict]:
    """Extract USA USD/MT price from ChemAnalyst regional price cards."""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    match = _USA_PRICE_RE.search(text)
    if match is None:
        match = _ANY_PRICE_RE.search(text)
    if match is None:
        return None

    try:
        price = float(match.group(1).replace(",", ""))
    except ValueError:
        return None

    if price <= 0:
        return None

    return {"price": price, "unit": "USD/MT"}


def fetch_price(chemical_name: str, url: str) -> Optional[dict]:
    try:
        html = _fetch_html(url)
    except Exception as exc:
        log.error("chemanalyst_fetch_failed", extra={"chemical_name": chemical_name, "error": str(exc)})
        return None

    parsed = _parse_price_table(html)
    if parsed is None:
        log.warning(
            "chemanalyst_parse_failed",
            extra={"chemical_name": chemical_name, "url": url},
        )
        return None

    return {
        "chemical_name": chemical_name,
        "price": parsed["price"],
        "unit": parsed["unit"],
        "currency": "USD",
        "date_recorded": date.today(),
        "source": "chemanalyst",
        "source_url": url,
    }


def fetch_all(chemical_names: Optional[list[str]] = None) -> list[dict]:
    """Fetch configured ChemAnalyst targets, optionally filtered by name."""
    targets = CHEMANALYST_TARGETS
    if chemical_names is not None:
        allowed = set(chemical_names)
        targets = {k: v for k, v in targets.items() if k in allowed}

    results = []
    for chemical_name, url in targets.items():
        record = fetch_price(chemical_name, url)
        if record:
            results.append(record)
        time.sleep(config.REQUEST_DELAY_SECONDS)
    return results
