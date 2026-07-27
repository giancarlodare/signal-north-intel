-- ============================================================================
-- Wave 3 stage 3: watches, the append-only event log, and saved items.
-- Decisions (operator walkthrough 2026-07-27):
--   A. Watches match GATE-CLEARED signals only: the daily matcher's universe
--      is signals a member session can actually read (public-safety, included
--      in a published brief). A member is never notified about a row the RLS
--      would refuse them.
--   B. A new watch backfills 30 days of matches, written as event_type
--      'backfill' so the "we told you first" log never claims a catch-up item
--      was surfaced ahead of time. Only 'match' events are told-you-first.
--   C. In-app delivery now; the weekly email digest reads watch_events later
--      (send provider + template are separate operator inputs).
--
-- APPLY AT OPERATOR GO (same paste session as the other Wave 3 migrations;
-- requires sn_role() from stage 1). Owner-scoped RLS throughout: a member
-- reads and writes ONLY their own rows; the operator sees all (support); the
-- match/backfill writers use the service role and bypass RLS.
--
-- Idempotent (create if not exists; policies dropped by name).
-- Rollback: drop table saved_items, watch_events, member_watches.
-- ============================================================================

begin;

-- 1. Standing follows: a keyword or a buyer. One row per follow.
create table if not exists member_watches (
  id              uuid primary key default gen_random_uuid(),
  member_id       uuid not null references auth.users(id) on delete cascade,
  kind            text not null check (kind in ('keyword', 'buyer')),
  keyword         text,
  organization_id uuid references organizations(id),
  created_at      timestamptz not null default now(),
  check ((kind = 'keyword' and keyword is not null and organization_id is null)
      or (kind = 'buyer' and organization_id is not null and keyword is null))
);
create unique index if not exists member_watches_kw_uniq
  on member_watches (member_id, kind, coalesce(lower(keyword), ''),
                     coalesce(organization_id, '00000000-0000-0000-0000-000000000000'));

-- 2. Append-only event log: what fired, when, for whom. 'match' events are
--    the "we told you first" substrate; 'backfill' is labelled catch-up;
--    'follow' records the member's own action. Never updated, never deleted.
create table if not exists watch_events (
  id          uuid primary key default gen_random_uuid(),
  member_id   uuid not null references auth.users(id) on delete cascade,
  watch_id    uuid references member_watches(id) on delete set null,
  signal_id   uuid references signals(id),
  event_type  text not null check (event_type in ('match', 'backfill', 'follow')),
  detail      text,
  created_at  timestamptz not null default now()
);
-- One match per (watch, signal): reruns of the matcher are no-ops.
create unique index if not exists watch_events_match_uniq
  on watch_events (watch_id, signal_id, event_type)
  where signal_id is not null;

-- 3. Saved items: a point-in-time bookmark of a Weekly Signal item. NOT an
--    event and NOT a watch (operator scoping 2026-07-27).
create table if not exists saved_items (
  member_id     uuid not null references auth.users(id) on delete cascade,
  brief_item_id uuid not null references brief_items(id) on delete cascade,
  saved_at      timestamptz not null default now(),
  primary key (member_id, brief_item_id)
);

-- 4. Owner-scoped RLS. Pattern per stage 1: permissive owner grant plus a
--    RESTRICTIVE clamp so no legacy-broad policy can widen access.
do $$
declare t text;
begin
  foreach t in array array['member_watches', 'watch_events', 'saved_items']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists sn_owner_read on public.%I', t);
    execute format(
      'create policy sn_owner_read on public.%I for select to authenticated
       using (public.sn_role() = ''operator'' or member_id = auth.uid())', t);
    execute format('drop policy if exists sn_owner_clamp on public.%I', t);
    execute format(
      'create policy sn_owner_clamp on public.%I as restrictive
       for select to authenticated
       using (public.sn_role() = ''operator'' or member_id = auth.uid())', t);
  end loop;
end $$;

-- Writes: members manage their own watches and saved items directly (the
-- app runs on the anon key under RLS).
drop policy if exists sn_owner_insert on member_watches;
create policy sn_owner_insert on member_watches
  for insert to authenticated with check (member_id = auth.uid());
drop policy if exists sn_owner_delete on member_watches;
create policy sn_owner_delete on member_watches
  for delete to authenticated using (member_id = auth.uid());

drop policy if exists sn_owner_insert on saved_items;
create policy sn_owner_insert on saved_items
  for insert to authenticated with check (member_id = auth.uid());
drop policy if exists sn_owner_delete on saved_items;
create policy sn_owner_delete on saved_items
  for delete to authenticated using (member_id = auth.uid());

-- The event log: members may append ONLY their own 'follow' records; match
-- and backfill events come from the service-role writer. No member UPDATE or
-- DELETE anywhere: append-only.
drop policy if exists sn_owner_insert on watch_events;
create policy sn_owner_insert on watch_events
  for insert to authenticated
  with check (member_id = auth.uid() and event_type = 'follow');

commit;
