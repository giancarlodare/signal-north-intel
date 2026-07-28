-- ============================================================================
-- Wave 3 next stage: the member "closing soon" live surface projection table
-- (docs/wave3-live-surface-design.md, operator approved D1-D4 2026-07-28).
--
-- WHY A PROJECTION TABLE (D1): we do NOT widen the member RLS on
-- signals/documents. Those carry operator-internal state (grades, review
-- stamps, suppression, unresolved orgs), and every widening of a policy on a
-- rich table is a new leak surface. This flat table holds ONLY gate-cleared
-- presentation columns, written by src/live_surface.py (deterministic, no
-- LLM); the database physically cannot leak what the table does not contain.
-- The slice gate lives in the writer -- one reviewable, unit-tested file --
-- not in policy predicates spread across tables.
--
-- v1 columns (D3): presentation only. NO grades, NO review state, NO amounts.
-- signal_id is carried for future watch linkage (D4, deferred) but is not a
-- readable rich-table key by itself under the member policy.
--
-- APPLY AT OPERATOR GO, after the validation dry-run table clears. The writer
-- self-skips until this table exists, so wiring it into daily-collect before
-- the paste never turns the pipeline red.
-- ============================================================================
begin;

create table if not exists member_live_items (
  id               uuid primary key default gen_random_uuid(),
  signal_id        uuid not null references signals(id) on delete cascade,
  headline         text not null,
  buyer_name       text,
  doc_type         text not null,
  closing_on       date not null,
  date_precision   text not null default 'day',
  reference_number text,
  url              text,
  category_slug    text,
  defence_relevant boolean not null default false,
  refreshed_at     timestamptz not null default now(),
  -- one live row per signal: the writer deletes-and-rewrites, and this makes
  -- a double-write a loud unique violation rather than a silent duplicate.
  unique (signal_id)
);

create index if not exists idx_member_live_closing
  on member_live_items (closing_on asc);

alter table member_live_items enable row level security;

-- Member read: the table contains ONLY gate-cleared rows by construction, so
-- the read policy is a simple true. The gate is the writer, not this policy.
drop policy if exists sn_live_read on member_live_items;
create policy sn_live_read on member_live_items
  for select to authenticated using (true);

-- Writes are service_role only (the daily job bypasses RLS). Restrictive
-- clamps so no authenticated member can ever insert/update/delete, matching
-- every other member-visible table.
drop policy if exists sn_live_write_insert on member_live_items;
create policy sn_live_write_insert on member_live_items as restrictive
  for insert to authenticated with check (false);
drop policy if exists sn_live_write_update on member_live_items;
create policy sn_live_write_update on member_live_items as restrictive
  for update to authenticated using (false);
drop policy if exists sn_live_write_delete on member_live_items;
create policy sn_live_write_delete on member_live_items as restrictive
  for delete to authenticated using (false);

grant select on table member_live_items to authenticated;

commit;
