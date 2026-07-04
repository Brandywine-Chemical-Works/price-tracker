# Systems Guide (Plain English)

For Radek — no technical background needed.

## What this is

A tool that checks chemical prices automatically, every weekday morning, and
tells you when something moves enough to matter.

## The three moving parts

**1. The scraper.** A small program that visits a couple of price-tracking
websites every weekday at 8am, reads the current price for each chemical
we're watching, and saves it. You don't do anything for this to happen — it
runs on its own.

**2. The database (Supabase).** Every price the scraper collects gets saved
here, like a running spreadsheet. You can log in and look at it directly if
you want, or add/remove a chemical from the tracking list without touching
any code — just edit a row in the `chemicals_config` table.

**3. The dashboard.** A webpage you check each morning. It shows a card for
every tracked chemical: current price, how much it's moved in the last week,
and a color status (green = stable, amber = moving, red = alert fired
recently). Click any card to see a 30-day price chart.

## When you'll get an email

If a chemical's price moves more than 5% from its recent average, you'll get
an email immediately with the chemical name, old price, new price, and how
much it moved. You'll also get one daily summary email confirming the
scraper ran and what it found, so you know if something's broken even
without checking the dashboard.

## Changing an alert threshold

Log into Supabase, open the `chemicals_config` table, find the chemical, and
change the number in `alert_threshold_pct`. No code changes needed.

## If something looks wrong

- **Dashboard shows no data / old data:** the Supabase project may have
  paused from inactivity (happens after 7 days with no activity on the free
  tier). Log into Supabase — there will be a "Restore" button if this is the
  cause.
- **No alert emails arriving:** check SendGrid's dashboard for delivery
  issues, or check your spam folder.
- **Anything else:** contact the engineer who built this, or see the
  `docs/SETUP.md` troubleshooting notes.
