"""
Thin wrapper around the Supabase Python client. Handles inserts with
dedup (idempotent runs) and the queries the alert engine and dashboard need.
"""
from datetime import date, timedelta
from typing import Optional

from supabase import create_client, Client

from scraper import config
from scraper.logger_setup import get_logger

log = get_logger(__name__)

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SERVICE_KEY not set. See docs/SETUP.md."
            )
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    return _client


def get_active_chemicals() -> list[dict]:
    """Read the chemicals_config table Radek can edit without touching code."""
    client = get_client()
    resp = client.table("chemicals_config").select("*").eq("is_active", True).execute()
    return resp.data or []


def price_already_recorded(chemical_name: str, date_recorded: date, source: str) -> bool:
    """Dedup check: has this chemical/date/source combo already been inserted?"""
    client = get_client()
    resp = (
        client.table("chemical_prices")
        .select("id")
        .eq("chemical_name", chemical_name)
        .eq("date_recorded", str(date_recorded))
        .eq("source", source)
        .limit(1)
        .execute()
    )
    return len(resp.data or []) > 0


def insert_price(record: dict) -> bool:
    """
    Insert one normalized price record. Returns True if inserted, False if
    skipped as a duplicate. Expected keys: chemical_name, price, unit,
    currency, date_recorded, source, source_url.
    """
    if price_already_recorded(record["chemical_name"], record["date_recorded"], record["source"]):
        log.info(
            "skip_duplicate",
            extra={"chemical_name": record["chemical_name"], "date": str(record["date_recorded"])},
        )
        return False

    client = get_client()
    payload = {**record, "date_recorded": str(record["date_recorded"])}
    client.table("chemical_prices").insert(payload).execute()
    log.info(
        "price_inserted",
        extra={
            "chemical_name": record["chemical_name"],
            "price": record["price"],
            "source": record["source"],
        },
    )
    return True


def get_rolling_average(chemical_name: str, days: int = 7) -> Optional[float]:
    """7-day rolling average price for a chemical, across all sources."""
    client = get_client()
    cutoff = str(date.today() - timedelta(days=days))
    resp = (
        client.table("chemical_prices")
        .select("price")
        .eq("chemical_name", chemical_name)
        .gte("date_recorded", cutoff)
        .execute()
    )
    prices = [row["price"] for row in (resp.data or [])]
    if not prices:
        return None
    return sum(prices) / len(prices)


def get_latest_price(chemical_name: str) -> Optional[dict]:
    client = get_client()
    resp = (
        client.table("chemical_prices")
        .select("*")
        .eq("chemical_name", chemical_name)
        .order("date_recorded", desc=True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def log_alert(chemical_name: str, previous_price: float, current_price: float,
              percent_change: float, direction: str) -> None:
    client = get_client()
    client.table("price_alerts").insert({
        "chemical_name": chemical_name,
        "previous_price": previous_price,
        "current_price": current_price,
        "percent_change": percent_change,
        "direction": direction,
    }).execute()
