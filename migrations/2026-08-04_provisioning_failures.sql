-- ============================================================================
-- Provisioning failures: the reconciliation worklist behind checkout-first
-- (operator 2026-08-03, change A). ONE row per Stripe subscription that was
-- PAID but could not be turned into a working account by the webhook.
--
-- WHY THIS TABLE EXISTS. In the checkout-first flow a subscription is created
-- before any account exists; the webhook provisions the account from the
-- Stripe-verified email. When that provisioning cannot complete -- no email on
-- the session, the Supabase admin call errors, the price maps to no tier --
-- someone has paid us and cannot read what they paid for, and silence is the
-- worst possible outcome (operator standing rule: silent failure is the enemy).
--
-- So the webhook records the failure HERE and emails the operator directly.
-- This table is what makes that alarm LOUD BUT NOT NOISY:
--
--   * unique(stripe_subscription_id) + insert-on-conflict-do-nothing means the
--     operator is emailed ONCE per stranded subscription, not once per Stripe
--     retry (Stripe retries a 500 for ~3 days).
--   * alerted_at records that the email went out, so a later retry that still
--     cannot provision does not re-alarm.
--   * resolved_at is stamped when the subscription is finally provisioned,
--     whether by a successful Stripe retry or by the manual provision command
--     (web/scripts/provision-member.mjs). An unresolved row is the operator's
--     open worklist.
--
-- This is NOT a projection of Stripe (member_subscriptions is). It is an
-- operational log of the one thing Stripe cannot tell us: that our own
-- provisioning did not keep up with a payment.
-- ============================================================================
begin;

create table if not exists provisioning_failures (
  id                      uuid primary key default gen_random_uuid(),
  -- One row per stranded subscription. The unique constraint is what makes the
  -- webhook's insert idempotent across Stripe's retries.
  stripe_subscription_id  text not null unique,
  stripe_customer_id      text,
  -- The Stripe-verified email we tried (and failed) to provision from. NULL is
  -- itself a failure mode: a completed checkout that carried no email at all.
  email                   text,
  -- Best-effort tier/interval read from the subscription's price, for the
  -- operator's context. NULL when the price mapped to no configured tier
  -- (which is itself a common reason to be here).
  tier                    text,
  interval                text,
  -- Why provisioning could not complete, in words: 'no-email',
  -- 'provision-failed', 'unmapped-price', 'welcome-send-failed'. Free text so
  -- a new reason needs no migration.
  reason                  text not null,
  first_seen_at           timestamptz not null default now(),
  -- When the operator alarm email was sent for this row. NULL means the alarm
  -- has not gone out yet; the webhook sends it and stamps this in one step.
  alerted_at              timestamptz,
  -- Stamped when the subscription is finally provisioned. A row with a NULL
  -- resolved_at is open work.
  resolved_at             timestamptz,
  -- How it was resolved: 'stripe-retry' or 'manual'. Context for the log.
  resolved_by             text
);

create index if not exists idx_provisioning_failures_open
  on provisioning_failures (first_seen_at desc)
  where resolved_at is null;

alter table provisioning_failures enable row level security;

-- Reads are OPERATOR ONLY: this is a list of paying customers' addresses in a
-- failed state. No member and no anon ever reads it.
drop policy if exists sn_provfail_read on provisioning_failures;
create policy sn_provfail_read on provisioning_failures
  for select to authenticated
  using (public.sn_role() = 'operator');

-- Writes are SERVICE ROLE ONLY. The only writer is the webhook (and the manual
-- provision command, which also runs service-role). No authenticated session
-- may write, so restrictive clamps deny insert/update/delete to members.
drop policy if exists sn_provfail_no_insert on provisioning_failures;
create policy sn_provfail_no_insert on provisioning_failures as restrictive
  for insert to authenticated with check (false);
drop policy if exists sn_provfail_no_update on provisioning_failures;
create policy sn_provfail_no_update on provisioning_failures as restrictive
  for update to authenticated using (false);
drop policy if exists sn_provfail_no_delete on provisioning_failures;
create policy sn_provfail_no_delete on provisioning_failures as restrictive
  for delete to authenticated using (false);

grant select on table provisioning_failures to authenticated;

commit;
