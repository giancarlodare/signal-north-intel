-- ============================================================================
-- Wave 3 stage 1: member auth + RLS as the client-facing gate.
-- Design + decision points D1-D6: docs/wave3-stage1-auth-rls.md
--
-- APPLY AT OPERATOR GO (the DDL paste). NOT applied automatically; the
-- collectors/CI use the service role and bypass RLS, and the web app's role
-- layer stays dark (PORTAL_ENABLED=false) until this is pasted AND the flag
-- is flipped. Paste this whole file in one Supabase SQL editor tab, then
-- SIGN OUT AND BACK IN once (decision D4: the operator's JWT role claim
-- refreshes on token renewal).
--
-- The policies ARE the gate: member reads are scoped to published +
-- gate-cleared surfaces by the DATABASE, so no UI bug can leak internal
-- state. Every policy is named sn_* and dropped by name (rollback at the
-- foot of the design doc).
-- ============================================================================

begin;

-- 1. Role reader: fail-closed to 'member' when the claim is absent.
create or replace function public.sn_role() returns text
language sql stable as $$
  select coalesce(auth.jwt() -> 'app_metadata' ->> 'sn_role', 'member');
$$;

-- 2. Stamp the operator BEFORE the clamps (D4). Sign out/in afterward.
update auth.users
   set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb)
       || '{"sn_role": "operator"}'::jsonb
 where email = 'giancarlo97dare@gmail.com';

-- 3. OPERATOR-ONLY tables: enable RLS, guarantee the operator full access
--    (permissive), clamp everyone else (restrictive). Skips tables that do
--    not exist yet (e.g. demand_arc_profiles pre-enablement).
do $$
declare t text;
begin
  foreach t in array array[
    'procurements','procurement_signals','predictions','prediction_anchors',
    'prediction_outcomes','prediction_supersessions','prospects',
    'prospect_interactions','discovered_entities','discovered_sources',
    'discovery_blocklist','evidence_grade_rungs','sources','contract_awards',
    'vendors']
  loop
    if to_regclass('public.' || t) is null then continue; end if;
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists sn_operator_all on public.%I', t);
    execute format(
      'create policy sn_operator_all on public.%I for all to authenticated
       using (public.sn_role() = ''operator'')
       with check (public.sn_role() = ''operator'')', t);
    execute format('drop policy if exists sn_operator_only on public.%I', t);
    execute format(
      'create policy sn_operator_only on public.%I as restrictive
       for select to authenticated
       using (public.sn_role() = ''operator'')', t);
  end loop;
end $$;

-- 4. MEMBER-VISIBLE tables: a permissive policy granting exactly the gated
--    subset, plus a RESTRICTIVE clamp so legacy-broad policies cannot leak
--    past the gate, plus operator-only writes.
do $$
declare
  t text;
  gate text;
begin
  for t, gate in select * from (values
    ('briefs',
     'status = ''published'''),
    ('brief_items',
     'included is true and exists (select 1 from public.briefs b
        where b.id = brief_items.brief_id and b.status = ''published'')'),
    ('signals',
     'exists (select 1 from public.brief_items bi
        join public.briefs b on b.id = bi.brief_id
        where bi.lead_signal_id = signals.id
          and bi.included and b.status = ''published'')'),
    ('documents',
     'exists (select 1 from public.signals s
        join public.brief_items bi on bi.lead_signal_id = s.id
        join public.briefs b on b.id = bi.brief_id
        where s.document_id = documents.id
          and bi.included and b.status = ''published'')'),
    ('organizations', 'true'),
    ('categories', 'true'),
    ('demand_arc_profiles',
     'significance = ''published''')
  ) as v(tname, cond)
  loop
    if to_regclass('public.' || t) is null then continue; end if;
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists sn_member_read on public.%I', t);
    execute format(
      'create policy sn_member_read on public.%I for select to authenticated
       using (public.sn_role() = ''operator'' or (%s))', t, gate);
    execute format('drop policy if exists sn_gate_clamp on public.%I', t);
    execute format(
      'create policy sn_gate_clamp on public.%I as restrictive
       for select to authenticated
       using (public.sn_role() = ''operator'' or (%s))', t, gate);
    execute format('drop policy if exists sn_write_insert on public.%I', t);
    execute format(
      'create policy sn_write_insert on public.%I as restrictive
       for insert to authenticated
       with check (public.sn_role() = ''operator'')', t);
    execute format('drop policy if exists sn_write_update on public.%I', t);
    execute format(
      'create policy sn_write_update on public.%I as restrictive
       for update to authenticated
       using (public.sn_role() = ''operator'')', t);
    execute format('drop policy if exists sn_write_delete on public.%I', t);
    execute format(
      'create policy sn_write_delete on public.%I as restrictive
       for delete to authenticated
       using (public.sn_role() = ''operator'')', t);
  end loop;
end $$;

commit;
