-- ============================================================================
-- Local subscription state, fed by the Stripe webhook (operator 2026-08-01).
--
-- WHY A LOCAL TABLE AT ALL. Stripe remains the SOURCE OF TRUTH: nothing here
-- is authored by us, every row is a projection of a Stripe subscription, and a
-- disagreement is resolved in Stripe's favour by replaying the webhook. What
-- this table buys is that the portal guard can answer "may this member read
-- the portal" from one indexed local row instead of a network call to Stripe
-- on every page render. A guard that depends on a third-party API being up is
-- a guard that fails open or fails slow, and neither is acceptable.
--
-- SCOPE (operator 2026-08-01, happy path only). Checkout session creation,
-- success redirect, and this state. Deliberately NOT built: self-serve
-- cancellation, plan changes, upgrade/downgrade, dunning, failed-payment
-- recovery. At ten subscribers those are Stripe dashboard tasks, and they are
-- where the subtle state-sync bugs live.
--
-- BUT the webhook still handles subscription.updated and .deleted, and that is
-- not a scope violation: those are how the operator's MANUAL dashboard actions
-- land here. Without them, cancelling a member in Stripe would leave their
-- portal access on forever. Handling the event is not building the flow.
-- ============================================================================
begin;

create table if not exists member_subscriptions (
  -- One row per member. A member with two Stripe subscriptions is an operator
  -- problem to resolve in the dashboard, not a state this table represents.
  member_id            uuid primary key references auth.users(id) on delete cascade,
  stripe_customer_id   text,
  stripe_subscription_id text unique,
  tier                 text not null check (tier in ('weekly', 'pro', 'founding')),
  interval             text not null check (interval in ('annual', 'monthly')),
  -- Stripe's own status string, stored verbatim rather than reduced to a
  -- boolean. 'active' and 'trialing' grant access; everything else does not,
  -- and keeping the raw value means a future rule can be written without a
  -- migration and without guessing what 'past_due' had been collapsed into.
  status               text not null,
  current_period_end   timestamptz,
  -- Stripe delivers out of order and retries. The webhook refuses to apply an
  -- event older than the row it would overwrite, so a late-arriving stale
  -- event cannot resurrect a cancelled subscription.
  event_created_at     timestamptz not null,
  updated_at           timestamptz not null default now()
);

create index if not exists idx_member_subs_status
  on member_subscriptions (status);

alter table member_subscriptions enable row level security;

-- A member may read THEIR OWN row: the account page shows what they are
-- paying for. Nobody reads anyone else's.
drop policy if exists sn_sub_read on member_subscriptions;
create policy sn_sub_read on member_subscriptions
  for select to authenticated
  using (public.sn_role() = 'operator' or member_id = auth.uid());

-- Writes are SERVICE ROLE ONLY, with no exception for the operator UI. The
-- only writer is the webhook, because the only author is Stripe. Restrictive
-- clamps so no authenticated session can grant itself a subscription.
drop policy if exists sn_sub_no_insert on member_subscriptions;
create policy sn_sub_no_insert on member_subscriptions as restrictive
  for insert to authenticated with check (false);
drop policy if exists sn_sub_no_update on member_subscriptions;
create policy sn_sub_no_update on member_subscriptions as restrictive
  for update to authenticated using (false);
drop policy if exists sn_sub_no_delete on member_subscriptions;
create policy sn_sub_no_delete on member_subscriptions as restrictive
  for delete to authenticated using (false);

grant select on table member_subscriptions to authenticated;

commit;
