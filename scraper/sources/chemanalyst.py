"""
ChemAnalyst price page scraper (static HTML + BeautifulSoup).

IMPORTANT: ChemAnalyst's page markup changes over time, and its price pages
for individual chemicals require checking their current URL pattern and
robots.txt before pointing this at production. This module is written so
the *pipeline* (fetch -> parse -> normalize -> hand to db.py) is complete
and correct; the CSS selectors in `_parse_price_table` are the one piece
you should verify/adjust against the live page before relying on it,
since selectors are exactly the kind of thing that breaks silently.

Steps before running against the real site:
  1. curl https://www.chemanalyst.com/robots.txt  and confirm the target
     path isn't disallowed.
  2. View source on the live product price page and confirm the table/row
     structure below still matches.
"""
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

# One entry per chemical this source covers. Update URLs to the real,
# current ChemAnalyst product page for each chemical.
CHEMANALYST_TARGETS = {
    "Methanol": "https://www.chemanalyst.com/Pricing-data/methanol-1",
    "Acetone": "https://www.chemanalyst.com/Pricing-data/acetone-2",
    "Sulfuric Acid": "https://www.chemanalyst.com/Pricing-data/sulphuric-acid-64",
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_html(url: str) -> str:
    headers = {"User-Agent": _ua.random}
    resp = requests.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.text


def _parse_price_table(html: str) -> Optional[dict]:
    """
    Parse the price + unit out of the page. Adjust the selectors below to
    match ChemAnalyst's current markup — verify with your browser's
    'Inspect Element' on the live price page.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Common pattern on price-tracking sites: a prominent price element
    # with a class like "price-value" or inside a summary card. Update this
    # selector after inspecting the live page.
    price_el = soup.select_one(".price-value, .current-price, [data-price]")
    unit_el = soup.select_one(".price-unit, .unit")

    if price_el is None:
        return None

    price_text = price_el.get_text(strip=True).replace(",", "").replace("$", "")
    try:
        price = float("".join(ch for ch in price_text if ch.isdigit() or ch == "."))
    except ValueError:
        return None

    unit = unit_el.get_text(strip=True) if unit_el else "USD/MT"
    return {"price": price, "unit": unit}


def fetch_price(chemical_name: str, url: str) -> Optional[dict]:
    try:
        html = _fetch_html(url)
    except Exception as exc:
        log.error("chemanalyst_fetch_failed", extra={"chemical_name": chemical_name, "error": str(exc)})
        return None

    parsed = _parse_price_table(html)
    if parsed is None:
        log.warning(
            "chemanalyst_parse_failed_check_selectors",
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
    """Fetch every chemical in CHEMANALYST_TARGETS (or a filtered subset)."""
    results = []
    targets = CHEMANALYST_TARGETS
    if chemical_names:
        targets = {k: v for k, v in targets.items() if k in chemical_names}

    for chemical_name, url in targets.items():
        record = fetch_price(chemical_name, url)
        if record:
            results.append(record)
        time.sleep(config.REQUEST_DELAY_SECONDS)  # politeness delay
    return results
