-- ============================================================================
-- Tier inquiries: the demand instrument behind the closed pricing columns
-- (operator 2026-08-01).
--
-- ONE table for both closed tiers, distinguished by `tier`, per the operator's
-- scoping: "same table, a tier column is enough to distinguish them."
--
--   pro         a Request-early-access click. Tracked as AGGREGATE interest:
--               the question it answers is whether Pro is worth finishing on
--               the assumed timeline.
--   enterprise  a Get-a-quote submission. Read INDIVIDUALLY and replied to
--               personally, so it carries the full qualifying detail and is
--               flagged distinctly in every read (see the operator view at the
--               bottom of this file).
--
-- WHAT THIS IS NOT: there is no Stripe product, price, or checkout for
-- Enterprise, deliberately (operator 2026-08-01). An Enterprise deal is
-- invoiced by hand the day it closes, and portal access is provisioned
-- manually the way founding members are. This table captures INTENT only; it
-- confers nothing and grants no access.
--
-- ACCESS SHAPE. The marketing site is public and unauthenticated, so the
-- insert must be reachable by `anon`. The grant is deliberately asymmetric:
--   INSERT  yes, for anon -- a visitor can leave their details
--   SELECT  no, for anyone but the operator -- a visitor can never read the
--           table back, so one prospect can never enumerate the others
-- That asymmetry is the whole security model here, and it is expressed in RLS
-- rather than in the form, per the standing rule that the database is the gate.
--
-- SPAM POSTURE: a public insert endpoint is a spam surface. Mitigated in the
-- server action by a honeypot field and length caps, not by a captcha. If bots
-- find it, the next step is a rate limit keyed on IP, not a widened gate.
-- ============================================================================
begin;

create table if not exists tier_inquiries (
  id            uuid primary key default gen_random_uuid(),
  tier          text not null check (tier in ('pro', 'enterprise')),
  email         text not null,
  -- Enterprise supplies all of these; Pro supplies email + tier only, so
  -- everything below is nullable by design rather than by omission.
  company_name  text,
  needs         text,
  seat_count    integer,
  timeline      text,
  -- Operator workflow on the individually-read Enterprise rows.
  status        text not null default 'new'
                  check (status in ('new', 'replied', 'closed', 'spam')),
  operator_note text,
  created_at    timestamptz not null default now()
);

create index if not exists idx_tier_inquiries_tier_created
  on tier_inquiries (tier, created_at desc);

alter table tier_inquiries enable row level security;

-- Anyone (including anon) may leave an inquiry. `with check` constrains what
-- they may write: only the two valid tiers, and never a status other than the
-- default, so a submitter cannot mark their own row replied or closed.
drop policy if exists sn_inquiry_insert on tier_inquiries;
create policy sn_inquiry_insert on tier_inquiries
  for insert to anon, authenticated
  with check (tier in ('pro', 'enterprise') and status = 'new');

-- Reads are OPERATOR ONLY. No member, and certainly no anon, ever sees this
-- table: it holds other prospects' contact details.
drop policy if exists sn_inquiry_read on tier_inquiries;
create policy sn_inquiry_read on tier_inquiries
  for select to authenticated
  using (public.sn_role() = 'operator');

-- Updates (status, operator_note) are operator only. No delete policy at all:
-- an inquiry is a record, and spam is marked, not erased.
drop policy if exists sn_inquiry_update on tier_inquiries;
create policy sn_inquiry_update on tier_inquiries
  for update to authenticated
  using (public.sn_role() = 'operator')
  with check (public.sn_role() = 'operator');

grant insert on table tier_inquiries to anon, authenticated;
grant select, update on table tier_inquiries to authenticated;

commit;
