# Setup Guide: Connecting Everything

This walks through every account and connection needed to make this repo
actually run: GitHub, Supabase, and SendGrid. Do these in order.

## 1. GitHub

1. Create (or use) a GitHub organization for Brandywine, e.g. `brandywine-chemical-works`.
2. Create a **private** repo named `brandywine-infrastructure`.
3. Push this code:
   ```bash
   cd brandywine-infrastructure
   git init
   git add .
   git commit -m "Initial commit: Project 1 price tracker"
   git branch -M main
   git remote add origin https://github.com/<org>/brandywine-infrastructure.git
   git push -u origin main
   ```
4. Settings > Branches > add a branch protection rule on `main` (require PR
   review before merge, at minimum for when a second engineer joins).
5. Settings > Secrets and variables > Actions > **New repository secret** —
   add each of these (values come from steps 2–3 below):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `SENDGRID_API_KEY`
   - `ALERT_EMAIL_FROM`
   - `ALERT_EMAIL_TO`

   These are what `.github/workflows/scrape.yml` reads at run time. Never
   commit these values into the repo itself — GitHub Actions Secrets are
   the only place they should live outside your local `.env`.

## 2. Supabase

1. Go to [supabase.com](https://supabase.com) and sign up using a Brandywine
   Google account (not a personal one — this needs to be handed off later).
2. Create a new project (pick a region close to Brandywine's users; free tier
   is fine).
3. Once provisioned, go to **SQL Editor > New Query**, paste in the contents
   of `supabase/schema.sql`, and run it. This creates `chemicals_config`,
   `chemical_prices`, and `price_alerts`, seeds a few starter chemicals, and
   enables Row Level Security with public read-only policies.
4. Go to **Project Settings > API**. You'll need two different keys for two
   different purposes:
   - **`service_role` key** → goes in `SUPABASE_SERVICE_KEY` (GitHub Secret
     and local `.env`). This is what the scraper uses server-side to write
     data. It bypasses RLS, so it must never appear in any file that ships
     to the browser.
   - **`anon` / `public` key** → goes directly into `dashboard/app.js`
     (`SUPABASE_ANON_KEY`). This is safe to expose client-side because RLS
     policies restrict it to read-only.
5. Add a second team member (Radek) as a project member under
   **Project Settings > Team** so there's an admin login that isn't tied to
   your personal account.
6. **Known gotcha**: Supabase free-tier projects pause after 7 days of
   inactivity. If the dashboard suddenly shows no data, check the Supabase
   project dashboard for a "paused" banner and click Restore.

## 3. SendGrid (email alerts)

1. Sign up at [sendgrid.com](https://sendgrid.com) with a Brandywine email —
   free tier covers 100 emails/day, plenty for daily alerts + health checks.
2. Settings > **Sender Authentication** > verify a single sender email (e.g.
   `alerts@brandywinechemicalworks.com`, or the Gmail address if no custom
   domain exists yet). SendGrid will reject sends from unverified senders.
3. Settings > **API Keys** > Create API Key > "Restricted Access" > grant
   only **Mail Send** permission. Copy the key immediately (shown once) into
   `SENDGRID_API_KEY`.
4. Test locally before relying on GitHub Actions:
   ```bash
   python -c "
   from scraper.alerts import _send_email
   _send_email('Test', 'If you got this, SendGrid works.')
   "
   ```

## 4. Dashboard deployment (GitHub Pages)

1. In `dashboard/app.js`, replace `SUPABASE_URL` and `SUPABASE_ANON_KEY`
   placeholders with your real values (the anon key, never service_role).
2. Repo Settings > Pages > Source: deploy from `main` branch, `/dashboard`
   folder (or move `dashboard/` contents to a separate repo if preferred —
   the README's suggested layout keeps it in one repo for simplicity).
3. GitHub will give you a live URL like
   `https://<org>.github.io/brandywine-infrastructure/`.

## 5. First run checklist

- [ ] `schema.sql` run successfully in Supabase, 3 tables visible in Table Editor
- [ ] `.env` filled in locally, `python -m scraper.main` runs without error
- [ ] `chemical_prices` table has rows after a local run
- [ ] GitHub Secrets configured, workflow manually triggered via
      Actions tab > Chemical Price Scraper > Run workflow
- [ ] Health-check email received
- [ ] Dashboard loads real data at the GitHub Pages URL
