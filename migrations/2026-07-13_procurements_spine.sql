-- ============================================================================
-- Phase A2: the procurement spine.
--
-- A prediction says "Company X will advance on Procurement Y." Signals today
-- attach to documents and organizations, but there is no entity for a NAMED
-- opportunity that accumulates evidence over time and climbs the demand-
-- strength ladder. This adds it, plus the link table that ties signals to it.
--
-- Two tables:
--   procurements        a named opportunity (buyer, title, scope, reference
--                       number, jurisdiction, category, current_stage 1..5
--                       mirroring the evidence-grade ladder, lifecycle status)
--   procurement_signals many-to-many procurement <-> signal, with soft-detach
--                       (no row deletion anywhere, per house rule)
--
-- IDENTITY (operator decision Q5, 2026-07-13): keyed on resolved buyer plus
-- scope plus reference-number WHERE PRESENT, human-confirmed at approval,
-- never auto-merged on fuzzy match. A reference number (a solicitation or
-- CanadaBuys number) is the hard key when present: a partial unique index
-- enforces one procurement per reference number so the proposer is idempotent
-- and can never mint a duplicate for a known reference. When absent, buyer +
-- scope is the human-reviewed proposal basis with no DB uniqueness; fuzzy
-- title similarity only ranks candidates for the reviewer and merges nothing.
--
-- MERGES are non-destructive: a duplicate is marked status='merged' and points
-- at the survivor via merged_into_id. Nothing is deleted, matching the review,
-- prospects, and discovery pages.
--
-- current_stage is DERIVED (the highest evidence_grade among linked, active
-- signals) but STORED, maintained explicitly by the proposer and the app
-- rather than by a trigger, so stage changes are auditable events. It is not
-- computed on read.
--
-- Propose-then-approve, same discipline as discovery: the proposer
-- (service_role) writes candidate procurements and links; the reviewer
-- (authenticated) confirms, edits, merges, and links by hand. The proposer
-- never confirms its own proposals.
--
-- Additive, transactional, idempotent. RLS + base grants inline
-- (the 2026-07-10 lesson). No collector, workflow, or extraction path touched.
-- ============================================================================
begin;

-- ---- procurements -----------------------------------------------------------
create table if not exists procurements (
  id                     uuid primary key default gen_random_uuid(),
  buyer_organization_id  uuid references organizations(id),
  unresolved_buyer_name  text,                 -- when the buyer is not yet an org row
  title                  text not null,
  scope                  text,                 -- what is being bought (identity component)
  reference_number       text,                 -- hard identity key when present
  jurisdiction           jurisdiction_level,
  category_id            uuid references categories(id),
  description            text,
  current_stage          smallint not null default 1
                           check (current_stage between 1 and 5),
  status                 text not null default 'proposed'
                           check (status in ('proposed','confirmed','rejected','merged')),
  merged_into_id         uuid references procurements(id),
  first_seen_on          date not null default current_date,
  last_seen_on           date not null default current_date,
  proposed_by            text not null default 'procurement-proposer@v1',
  review_note            text,
  reviewed_at            timestamptz,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now(),
  -- a merged row must name its survivor; a non-merged row must not
  check ((status = 'merged') = (merged_into_id is not null))
);

-- Hard identity key: one procurement per reference number (case-insensitive),
-- only where a reference number exists. Absent references are human-resolved,
-- so they are deliberately not constrained here.
create unique index if not exists uq_procurements_reference
  on procurements (lower(reference_number))
  where reference_number is not null;

create index if not exists idx_procurements_buyer
  on procurements (buyer_organization_id);
create index if not exists idx_procurements_status_stage
  on procurements (status, current_stage desc);

drop trigger if exists trg_procurements_updated on procurements;
create trigger trg_procurements_updated before update on procurements
  for each row execute function set_updated_at();

-- ---- procurement_signals ----------------------------------------------------
create table if not exists procurement_signals (
  id             uuid primary key default gen_random_uuid(),
  procurement_id uuid not null references procurements(id) on delete cascade,
  signal_id      uuid not null references signals(id) on delete cascade,
  linked_by      text not null default 'procurement-proposer@v1',  -- or 'human'
  active         boolean not null default true,   -- soft-detach; never row-deleted
  created_at     timestamptz not null default now(),
  unique (procurement_id, signal_id)
);

create index if not exists idx_procsignals_procurement
  on procurement_signals (procurement_id) where active;
create index if not exists idx_procsignals_signal
  on procurement_signals (signal_id) where active;

-- ---- RLS + grants (both layers together) ------------------------------------
alter table procurements        enable row level security;
alter table procurement_signals enable row level security;

-- procurements: reviewer reads all, may create/confirm/merge/edit. The
-- proposer runs as service_role and bypasses RLS.
drop policy if exists "proc_read"   on procurements;
create policy "proc_read"   on procurements for select to authenticated using (true);
drop policy if exists "proc_insert" on procurements;
create policy "proc_insert" on procurements for insert to authenticated with check (true);
drop policy if exists "proc_update" on procurements;
create policy "proc_update" on procurements for update to authenticated using (true) with check (true);

-- links: reviewer reads all, may link a signal by hand and soft-detach
-- (update active). No delete, matching every other page.
drop policy if exists "procsig_read"   on procurement_signals;
create policy "procsig_read"   on procurement_signals for select to authenticated using (true);
drop policy if exists "procsig_insert" on procurement_signals;
create policy "procsig_insert" on procurement_signals for insert to authenticated with check (true);
drop policy if exists "procsig_update" on procurement_signals;
create policy "procsig_update" on procurement_signals for update to authenticated using (true) with check (true);

grant select, insert, update on table procurements        to authenticated;
grant select, insert, update on table procurement_signals to authenticated;
-- deliberately NO delete grants, and nothing to anon. service_role bypasses.

commit;
