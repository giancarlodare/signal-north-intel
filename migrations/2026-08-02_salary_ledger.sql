-- ============================================================================
-- Salary ledger: Layer-1 comparability tables (operator go 2026-08-02,
-- design: docs/sunshine-list-design.md).
--
-- Two DATASET tables, deliberately outside `documents`: hundreds of
-- thousands of rows per year would make the corpus unqueryable and bloat
-- what the extractor walks. Nothing here is member-facing; no extraction
-- path touches these tables; LLM spend is zero by design.
--
-- ACCESS SHAPE: service-role writes (the collector), operator-only reads.
-- No member policy at all: the comparator ledger is an operator instrument
-- until a product surface earns its own gated review.
-- ============================================================================
begin;

create table if not exists salary_disclosures (
  id               uuid primary key default gen_random_uuid(),
  year             integer not null check (year between 1996 and 2100),
  sector           text,
  employer         text not null,
  last_name        text not null,
  first_name       text not null,
  position         text not null,
  salary_paid      numeric(12,2) not null,
  taxable_benefits numeric(12,2),
  -- The exact annual source file, per the provenance discipline.
  source_url       text not null,
  ingested_at      timestamptz not null default now(),
  unique (year, employer, last_name, first_name, position)
);

create index if not exists idx_salary_year_employer
  on salary_disclosures (year, employer);

create table if not exists police_admin_stats (
  id          uuid primary key default gen_random_uuid(),
  year        integer not null check (year between 1960 and 2100),
  service     text not null,
  metric      text not null,
  value       numeric,
  source_url  text not null,
  ingested_at timestamptz not null default now(),
  unique (year, service, metric)
);

create index if not exists idx_police_admin_year_service
  on police_admin_stats (year, service);

alter table salary_disclosures enable row level security;
alter table police_admin_stats enable row level security;

-- Operator-only reads. The collector writes service-role, which bypasses
-- RLS, so no insert policy is granted to any client role at all.
drop policy if exists sn_salary_read on salary_disclosures;
create policy sn_salary_read on salary_disclosures
  for select to authenticated
  using (public.sn_role() = 'operator');

drop policy if exists sn_police_admin_read on police_admin_stats;
create policy sn_police_admin_read on police_admin_stats
  for select to authenticated
  using (public.sn_role() = 'operator');

grant select on table salary_disclosures to authenticated;
grant select on table police_admin_stats to authenticated;

commit;
