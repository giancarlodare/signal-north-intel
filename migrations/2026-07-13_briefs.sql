-- ============================================================================
-- briefs + brief_items: the Weekly Signal editorial surface (editorial model
-- Phase 3, docs/editorial-model-redesign.md section 4.4 / 7.1).
--
-- The generator writes a `draft` brief for the covered week with ranked items;
-- the operator edits at /brief (cut, reorder, add copy) and publishes; a
-- published brief is frozen and joins the prediction ledger as part of the
-- provable, time-stamped track record.
--
-- Clustering reuses the procurement spine: a brief_item is a cluster keyed by a
-- procurement (where the signal is already clustered), else an organization,
-- else a standalone signal.
--
-- Reviewed, transactional, idempotent (create-if-not-exists).
-- ============================================================================
begin;

create table if not exists briefs (
  id            uuid primary key default gen_random_uuid(),
  week_start    date not null unique,               -- Monday of the covered week
  status        text not null default 'draft'
                  check (status in ('draft', 'published')),
  title         text,
  intro         text,
  -- Threshold-tuning visibility: how many timing-relevant signals the
  -- materiality/grade bar excluded this week, and by which gate.
  excluded_below_threshold int not null default 0,
  exclusion_breakdown jsonb,                         -- {below_materiality, below_grade}
  created_at    timestamptz not null default now(),
  published_at  timestamptz                          -- set once at publish, frozen
);

create table if not exists brief_items (
  id            uuid primary key default gen_random_uuid(),
  brief_id      uuid not null references briefs(id) on delete cascade,
  cluster_kind  text not null
                  check (cluster_kind in ('procurement', 'organization', 'signal')),
  cluster_ref   uuid not null,                       -- procurement_id | organization_id | signal_id
  lead_signal_id uuid references signals(id),        -- strongest/soonest member
  timing_path   text not null
                  check (timing_path in ('recent', 'imminent')),
  soonest_date  date,                                -- driving published_on (ranking + why)
  included      boolean not null default true,       -- editor cut = false
  rank          int,                                 -- editor ordering
  headline_override text,
  editor_note   text,
  created_at    timestamptz not null default now(),
  unique (brief_id, cluster_kind, cluster_ref)
);

create index if not exists idx_brief_items_brief on brief_items (brief_id, rank);

-- The /brief editor (authenticated role) reads and edits briefs; the generator
-- uses service_role. Mirror the review-app grant/RLS pattern.
alter table briefs      enable row level security;
alter table brief_items enable row level security;

drop policy if exists "brief_read"   on briefs;
create policy "brief_read"   on briefs      for select to authenticated using (true);
drop policy if exists "brief_write"  on briefs;
create policy "brief_write"  on briefs      for update to authenticated using (true) with check (true);
drop policy if exists "brief_items_read"  on brief_items;
create policy "brief_items_read"  on brief_items for select to authenticated using (true);
drop policy if exists "brief_items_write" on brief_items;
create policy "brief_items_write" on brief_items for update to authenticated using (true) with check (true);

grant select, update on table briefs, brief_items to authenticated;

commit;
