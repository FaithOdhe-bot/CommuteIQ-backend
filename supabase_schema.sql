-- CommuteIQ — Supabase reports table
-- Run this in Supabase's SQL editor (Database → SQL Editor → New query)
--
-- If you already created the original table, run the ALTER statements
-- at the bottom instead of the full CREATE.

create table reports (
  id         bigint generated always as identity primary key,
  city       text           not null,
  type       text           not null,
  location   text           not null,
  lat        double precision,           -- anonymized to ~1.1km grid (2 decimal places)
  lng        double precision,           -- anonymized to ~1.1km grid (2 decimal places)
  timestamp  double precision,
  created_at double precision default extract(epoch from now()),
  expires_at double precision            -- unix timestamp when this report auto-expires
);

-- Index for fast city-filtered queries (used by GET /reports?city=lagos)
create index reports_city_idx     on reports(city);
create index reports_created_idx  on reports(created_at desc);
create index reports_expires_idx  on reports(expires_at);

-- ── If you already have the old table, run these instead ──────────────────
-- alter table reports add column if not exists lat        double precision;
-- alter table reports add column if not exists lng        double precision;
-- alter table reports add column if not exists expires_at double precision;
