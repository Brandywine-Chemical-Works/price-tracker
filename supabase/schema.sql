-- Brandywine Price Tracker: core schema
-- Run this in Supabase SQL Editor (Project > SQL Editor > New Query)

-- Chemicals being tracked, and their alert config.
-- Radek edits this table to add/remove chemicals without touching code.
create table if not exists chemicals_config (
    id bigint generated always as identity primary key,
    chemical_name text not null unique,
    category text,                          -- solvent, surfactant, agrochemical, etc.
    sources text[] not null default '{}',   -- e.g. {'chemanalyst','worldbank'}
    alert_threshold_pct numeric not null default 5.0,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

-- Every price reading, from every source, every run. Historical, append-only.
create table if not exists chemical_prices (
    id bigint generated always as identity primary key,
    chemical_name text not null,
    price numeric not null,
    unit text not null,                     -- normalized to price-per-metric-ton
    currency text not null default 'USD',
    date_recorded date not null,
    source text not null,
    source_url text,
    created_at timestamptz not null default now(),
    unique (chemical_name, date_recorded, source)   -- idempotency / dedup key
);

create index if not exists idx_chemical_prices_name_date    
    on chemical_prices (chemical_name, date_recorded desc);

-- Log of every alert email sent, for the CRM integration (Week 7) and
-- the dashboard's "Alert History" panel (Week 4).
create table if not exists price_alerts (
    id bigint generated always as identity primary key,
    chemical_name text not null,
    previous_price numeric not null,
    current_price numeric not null,
    percent_change numeric not null,
    direction text not null check (direction in ('up', 'down')),
    triggered_at timestamptz not null default now()
);

-- Seed a few chemicals to get started. Radek/finance intern expand this list.
insert into chemicals_config (chemical_name, category, sources, alert_threshold_pct)
values
    ('Methanol', 'solvent', '{"chemanalyst","worldbank"}', 5.0),
    ('Acetone', 'solvent', '{"chemanalyst"}', 5.0),
    ('Sulfuric Acid', 'industrial', '{"chemanalyst"}', 5.0)
on conflict (chemical_name) do nothing;

-- Row Level Security: enable once auth is wired up in Week 5+.
-- For now these tables are read via the service-role key from the backend
-- scraper, and read-only via anon key from the public dashboard.
alter table chemical_prices enable row level security;
alter table chemicals_config enable row level security;
alter table price_alerts enable row level security;

create policy "public read chemical_prices" on chemical_prices
    for select using (true);
create policy "public read chemicals_config" on chemicals_config
    for select using (true);
create policy "public read price_alerts" on price_alerts
    for select using (true);

-- Inserts/updates only happen via the service_role key (server-side scraper),
-- which bypasses RLS entirely, so no insert policy is needed for anon.
