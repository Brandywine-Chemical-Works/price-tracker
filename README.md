# Brandywine Infrastructure

Internal engineering repo for Brandywine Chemical Works LLC. Built as part of the
12-week Software Engineering Internship program (June–September 2026).

This repo currently contains **Project 1: Chemical Price Tracker**:

```
brandywine-infrastructure/
├── scraper/                 # Python scraping + data pipeline
│   ├── config.py            # Env config, chemical list, thresholds
│   ├── db.py                # Supabase client wrapper (insert, dedup, queries)
│   ├── logger_setup.py      # Structured JSON logging
│   ├── alerts.py            # Price movement detection + SendGrid email
│   ├── main.py               # Orchestrator entrypoint (run this)
│   └── sources/
│       ├── chemanalyst.py   # BeautifulSoup scraper (static HTML)
│       └── worldbank.py     # World Bank Commodity Prices REST API
├── supabase/
│   └── schema.sql           # Full DB schema: chemical_prices, chemicals_config
├── dashboard/                # Static HTML/JS dashboard (GitHub Pages)
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── .github/workflows/
│   └── scrape.yml           # Scheduled scraper (weekdays 8am UTC)
├── docs/
│   ├── SETUP.md              # Step-by-step: Supabase, SendGrid, GitHub setup
│   └── SYSTEMS_GUIDE.md      # Non-technical explainer (for Radek)
├── requirements.txt
└── .env.example
```

## Quick start (local dev)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your Supabase + SendGrid keys
python -m scraper.main
```

See `docs/SETUP.md` for the full walkthrough of connecting Supabase, GitHub
Actions, and SendGrid — none of this runs without those three accounts
configured.

## Architecture in one paragraph

A Python scraper pulls chemical prices from two sources (a scraped HTML page
and a free REST API), normalizes them into one schema, and writes them to a
Supabase (Postgres) table with a dedup check so re-runs are idempotent. A
GitHub Actions workflow runs the scraper on a cron schedule with zero server
required. After each run, `alerts.py` compares the new price to a rolling
7-day average per chemical and emails an alert via SendGrid if it moves past
a configurable threshold. A static dashboard (plain HTML/JS + Chart.js) reads
directly from Supabase using its JS client and is hosted free on GitHub
Pages — no backend of its own.
