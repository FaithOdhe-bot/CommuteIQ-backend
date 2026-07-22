-- Run this in Supabase's SQL editor to create the reports table.
create table reports (
  id bigint generated always as identity primary key,
  city text not null,
  type text not null,
  location text not null,
  timestamp double precision,
  created_at double precision default extract(epoch from now())
);
