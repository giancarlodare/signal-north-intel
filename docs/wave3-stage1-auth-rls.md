# Wave 3 Stage 1: member auth + RLS as the client-facing gate

Status: DESIGN for operator approval (2026-07-27). Build follows approval;
PR follows build; operator pastes the DDL below at merge time. Boundary:
functional layer only, no styling, no copy.

## The principle being implemented

The RLS policy set IS the client-facing gate (docs/client-facing-gate.md):
the DATABASE enforces "nothing reaches a member until it is defensible",
so no UI bug, forgotten filter, or future page can leak internal state to
a client. The UI's member filtering (stage 2) is a convenience layer over
a floor the database already guarantees.

## Decision points (D1-D6)

- **D1. Where the role lives (recommended: JWT app_metadata).**
  `sn_role` in the Supabase user's `app_metadata`, read in SQL via
  `auth.jwt()`. An account with NO role claim defaults to MEMBER:
  fail-closed, so a mis-provisioned account gets the least access, never
  the most. Alternative (a roles table) adds a join to every policy and a
  second provisioning step; not recommended.
- **D2. Enforcement style (recommended: RESTRICTIVE policies layered
  over the existing permissive ones).** Existing policies grant broad
  reads "to authenticated" (one role today). RESTRICTIVE policies AND
  onto every query, so the gate clamps legacy-broad policies without
  renaming or dropping any of them: additive, reversible, and no risk of
  breaking the operator app by missing a policy name.
- **D3. The member-visible surface (stages 1-2), everything else
  operator-only.** See the table below. Notably: `sources` is
  OPERATOR-ONLY (the collection map is our coverage boundary, internal
  per the gate doctrine; members reach publisher URLs through documents);
  `demand_arc_profiles` members see ONLY significance='published' rows
  (none exist yet, which is the honest state).
- **D4. Operator stamping + JWT refresh.** The DDL stamps the operator
  account (giancarlo97dare@gmail.com) with sn_role=operator BEFORE the
  clamps take effect. JWT claims refresh on token refresh: after pasting,
  SIGN OUT AND BACK IN on the review app once, or the operator session
  will read as member until the token renews.
- **D5. PORTAL_ENABLED.** A server-side env var in the web app (set in
  Vercel), default OFF. While off, member-facing routes 404; the operator
  app is not gated by it. No client-side exposure of the flag.
- **D6. Member provisioning.** Manual dashboard invites only while dark;
  members get `app_metadata.sn_role = "member"` at creation (or nothing,
  which is the same by D1). No open signup path is built.

## The member-visible surface

| Table | Member read | Gate condition |
|---|---|---|
| briefs | yes | status = 'published' only |
| brief_items | yes | parent brief published AND included = true |
| signals | yes | lead signal of an included item of a published brief |
| documents | yes | the document behind such a signal (provenance click-through) |
| organizations, categories | yes (read-only) | reference data; writes operator-only |
| demand_arc_profiles | yes | significance = 'published' rows only (the significance gate, verbatim) |
| everything else (procurements, procurement_signals, predictions + anchors/outcomes/supersessions, prospects + interactions, discovery tables, evidence_grade_rungs, sources, contract_awards, vendors) | NO | operator-only |

Member WRITES: none anywhere in stage 1 (watchlist writes arrive in
stage 3 with their own scoped policies).

## DDL (operator paste, one SQL editor tab, reads top to bottom)

```sql
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
```

Collectors and CI jobs are unaffected: they use the service role, which
bypasses RLS by design. The clamps bind only browser sessions.

## What the code side builds after approval (the PR)

- `sn_role` helper on the web server side (reads the session's
  app_metadata; defaults to member).
- `PORTAL_ENABLED` server-side flag; member routes 404 while off.
- Route-level guards: existing operator pages require operator; a
  member-route scaffold (unstyled, awaiting stage-2 data layer) requires
  member or operator AND the flag.
- A smoke test script (read-only) that signs in as a throwaway member and
  asserts: published-brief read works, procurements/predictions/sources
  reads return zero rows, no write path succeeds. The gate is verified by
  test, not assumed.

## Rollback

Every policy is named `sn_*` and dropped by name; `drop function
public.sn_role() cascade` plus dropping the sn_* policies restores the
prior state exactly. The stamps in auth.users are inert metadata.
