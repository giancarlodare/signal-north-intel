-- ============================================================================
-- Public-safety member-read gate: the SECOND, INDEPENDENT barrier.
-- docs/public-safety-relevance-filter-design.md (operator 2026-07-27).
--
-- Defence in depth. The brief lens (composition) already holds general
-- municipal items out of the member draft. This adds a barrier UNDER it: a
-- persisted signals.public_safety flag, derived by a SEPARATE pass
-- (src/apply_public_safety.py) that does not touch the brief generator, plus
-- RESTRICTIVE RLS clamps that AND onto the Wave-3 member gate. So even if the
-- lens breaks or a new composition path is added, a member session physically
-- cannot read a non-public-safety item: the database refuses it.
--
-- APPLY AT OPERATOR GO (the DDL paste), same as the Wave-3 stage-1 migration
-- and gated by the same PORTAL_ENABLED flip. Collectors/CI use the service
-- role and bypass RLS; the flag column is safe to add any time (default false =
-- fail-closed: a member sees a signal only once it is affirmatively derived
-- public-safety). Paste the whole file in one Supabase SQL editor tab.
--
-- FAIL-CLOSED: public_safety defaults false, so before the derivation pass runs
-- the member view is EMPTY, never over-broad. Run src/apply_public_safety.py
-- --apply after pasting to populate the flag across the corpus.
--
-- Idempotent (add-column IF NOT EXISTS; policies dropped by name then created).
-- Rollback: drop the three sn_public_safety_clamp policies and the column.
-- ============================================================================

begin;

-- 1. The persisted, independently-derived relevance flag. Default false is the
--    fail-closed floor: unpopulated -> not member-visible.
alter table signals
  add column if not exists public_safety boolean not null default false;

comment on column signals.public_safety is
  'Member-read gate (defence in depth): true iff the signal is public-safety-'
  'relevant, derived by src/apply_public_safety.py INDEPENDENTLY of the brief '
  'lens so a lens break cannot leak. Default false = fail-closed. See '
  'docs/public-safety-relevance-filter-design.md.';

-- 2. RESTRICTIVE clamps: they AND onto the Wave-3 sn_gate_clamp, so a member
--    read must satisfy BOTH the published/included gate AND public-safety
--    relevance. Operator (sn_role='operator') bypasses, exactly like the
--    existing clamps. Single-responsibility: each clamp adds ONLY the
--    public-safety condition; the published/included linkage is already
--    enforced by sn_gate_clamp on the same tables.
do $$
declare
  t text;
  cond text;
begin
  for t, cond in select * from (values
    -- A signal is member-visible only if it is itself public-safety.
    ('signals',
     'signals.public_safety'),
    -- A brief item is member-visible only if its lead signal is public-safety.
    ('brief_items',
     'exists (select 1 from public.signals s
        where s.id = brief_items.lead_signal_id and s.public_safety)'),
    -- A document is member-visible only if a public-safety signal cites it.
    ('documents',
     'exists (select 1 from public.signals s
        where s.document_id = documents.id and s.public_safety)')
  ) as v(tname, ccond)
  loop
    if to_regclass('public.' || t) is null then continue; end if;
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists sn_public_safety_clamp on public.%I', t);
    execute format(
      'create policy sn_public_safety_clamp on public.%I as restrictive
       for select to authenticated
       using (public.sn_role() = ''operator'' or (%s))', t, cond);
  end loop;
end $$;

commit;
