"""
Price movement alerting: compares each new reading to the chemical's rolling
7-day average and emails Radek via SendGrid if it moves past threshold.
Also sends a daily health-check email summarizing the run.
"""
from typing import Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from scraper import config, db
from scraper.logger_setup import get_logger

log = get_logger(__name__)


def _send_email(subject: str, plain_text_body: str) -> None:
    if not config.SENDGRID_API_KEY:
        log.warning("sendgrid_not_configured_skipping_email", extra={"subject": subject})
        return

    message = Mail(
        from_email=(config.ALERT_EMAIL_FROM, "Brandywine Price Tracker"),
        to_emails=config.ALERT_EMAIL_TO,
        subject=subject,
        plain_text_content=plain_text_body,
    )
    try:
        sg = SendGridAPIClient(config.SENDGRID_API_KEY)
        sg.send(message)
        log.info("email_sent", extra={"subject": subject})
    except Exception as exc:
        log.error("email_send_failed", extra={"subject": subject, "error": str(exc)})


def check_and_alert(chemical_name: str, new_price: float, threshold_pct: float) -> Optional[dict]:
    """
    Compare new_price to the rolling 7-day average. If the move exceeds
    threshold_pct, log the alert and send an email. Returns the alert dict
    if one fired, else None.
    """
    baseline = db.get_rolling_average(chemical_name, days=7)
    if baseline is None or baseline == 0:
        return None  # not enough history yet to compare against

    percent_change = ((new_price - baseline) / baseline) * 100
    if abs(percent_change) < threshold_pct:
        return None

    direction = "up" if percent_change > 0 else "down"
    db.log_alert(chemical_name, baseline, new_price, percent_change, direction)

    body = (
        f"Price Alert: {chemical_name}\n\n"
        f"Current price: {new_price:.2f}\n"
        f"7-day average: {baseline:.2f}\n"
        f"Change: {percent_change:+.1f}% ({direction})\n\n"
        f"This is an automated alert from the Brandywine Price Tracker.\n"
        f"To adjust this chemical's alert threshold, edit the chemicals_config "
        f"table in Supabase.\n"
        f"---\n"
        f"Brandywine Price Tracker | To stop these emails, update alert "
        f"settings in Supabase (chemicals_config.is_active)."
    )
    _send_email(f"Brandywine Price Alert: {chemical_name} {direction} {abs(percent_change):.1f}%", body)

    return {
        "chemical_name": chemical_name,
        "previous_price": baseline,
        "current_price": new_price,
        "percent_change": percent_change,
        "direction": direction,
    }


def send_health_check(scraped_count: int, failed_sources: list[str], alerts_fired: list[dict]) -> None:
    """Daily summary email so silent failures don't go undetected."""
    lines = [
        f"Brandywine Price Tracker — Daily Health Check",
        f"",
        f"Chemicals scraped successfully: {scraped_count}",
        f"Sources with failures: {', '.join(failed_sources) if failed_sources else 'none'}",
        f"Alerts fired today: {len(alerts_fired)}",
    ]
    for a in alerts_fired:
        lines.append(f"  - {a['chemical_name']}: {a['percent_change']:+.1f}% ({a['direction']})")

    _send_email("Brandywine Price Tracker: Daily Health Check", "\n".join(lines))
