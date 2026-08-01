-- Cost envelopes made BINDING (operator 2026-07-29).
--
-- Per-host token logging measures spend; it does not bind it. These two
-- tables are what src/envelope_guard.py reads before any extract-backfill
-- batch dispatches, so a batch that would exceed its declared envelope is
-- skipped and surfaced instead of run.
--
--   extraction_envelopes  the declared ceilings, one row per operator
--                         approval, with the amount and when it was approved.
--   extraction_spend      one row per real extraction run: the measured token
--                         counts, the computed cost, and the per-host split
--                         so a commingled batch stays attributable.
--
-- Service-role only. Nothing here is member-readable; RLS denies by default
-- and no policy is granted.

create table if not exists extraction_envelopes (
  key                    text primary key,
  label                  text not null,
  declared_usd           numeric(10,2) not null check (declared_usd > 0),
  -- The measured per-doc rate that priced the envelope at approval time.
  -- Used only until the envelope has runs of its own to measure from.
  seed_rate_usd_per_doc  numeric(10,6),
  -- open       spend is measured and the guard may certify batches
  -- unmeasured spend predates per-run logging; the guard REFUSES to certify
  --            (an unknown is not a zero) until it is re-declared
  -- closed     finished; reopening is an operator decision
  status                 text not null default 'open'
                         check (status in ('open', 'unmeasured', 'closed')),
  approved_on            date,
  approved_by            text,
  note                   text,
  created_at             timestamptz not null default now()
);

create table if not exists extraction_spend (
  id                     uuid primary key default gen_random_uuid(),
  envelope               text not null references extraction_envelopes(key),
  model                  text not null,
  documents_processed    integer not null default 0,
  input_tokens           bigint not null default 0,
  output_tokens          bigint not null default 0,
  cache_write_tokens     bigint not null default 0,
  cache_read_tokens      bigint not null default 0,
  cost_usd               numeric(12,4) not null default 0,
  -- {host: {docs, input_tokens, output_tokens, ...}}: keeps a run that mixes
  -- scopes attributable per source rather than estimable after the fact.
  usage_by_host          jsonb not null default '{}'::jsonb,
  run_url                text,
  recorded_at            timestamptz not null default now()
);

create index if not exists extraction_spend_envelope_idx
  on extraction_spend (envelope, recorded_at desc);

alter table extraction_envelopes enable row level security;
alter table extraction_spend enable row level security;

-- ---------------------------------------------------------------------------
-- Seeds. Amounts are the operator's own approvals, verbatim. No spend row is
-- seeded that was not actually measured.

-- Tier-3 awarded-history drain. Approved 2026-07-28 at a $45-65 envelope,
-- $52 point estimate, 2,182 docs at the measured $0.0240/doc. The ceiling is
-- what binds, so declared is 65.
insert into extraction_envelopes
  (key, label, declared_usd, seed_rate_usd_per_doc, status, approved_on,
   approved_by, note)
select 'tier3-awarded', 'Tier-3 awarded-history drain', 65.00, 0.024000,
       'open', date '2026-07-28', 'operator',
       'Approved as a $45-65 envelope with a $52 point estimate over 2,182 '
       'docs. Coverage/depth fuel, not a significance play.'
where not exists (select 1 from extraction_envelopes where key = 'tier3-awarded');

-- The unscoped drain, approved 2026-07-26 under the Toronto $63 read.
-- Deliberately seeded 'unmeasured': its batches ran BEFORE per-run token
-- logging landed (2026-07-28), so cumulative spend against it is a floor, not
-- a total. Seeding it 'open' with $0 spent would silently re-authorize the
-- whole $63. The guard refuses to certify against it until the operator
-- re-declares it with a fresh amount.
insert into extraction_envelopes
  (key, label, declared_usd, seed_rate_usd_per_doc, status, approved_on,
   approved_by, note)
select 'unscoped-drain-2026-07', 'Unscoped drain (Toronto $63 read)', 63.00,
       0.019400, 'unmeasured', date '2026-07-26', 'operator',
       'Spend against this envelope predates per-run token logging and is '
       'unmeasured. Requires re-declaration before any further dispatch.'
where not exists (select 1 from extraction_envelopes
                  where key = 'unscoped-drain-2026-07');

-- The two tier-3 batches that DID run under per-run logging, backfilled from
-- their own run logs (batch 1: $19.37/1,000 docs; batch 2: $19.16/1,000).
-- Token counts are left at zero because the logs recorded cost, not the
-- four-way token split; the cost figure is the measurement.
insert into extraction_spend
  (envelope, model, documents_processed, cost_usd, run_url, recorded_at)
select 'tier3-awarded', 'claude-opus-4-8', 1000, 19.3700,
       'backfilled from run log (batch 1)', timestamptz '2026-07-28 12:00:00+00'
where not exists (
  select 1 from extraction_spend
  where envelope = 'tier3-awarded' and run_url = 'backfilled from run log (batch 1)');

insert into extraction_spend
  (envelope, model, documents_processed, cost_usd, run_url, recorded_at)
select 'tier3-awarded', 'claude-opus-4-8', 1000, 19.1600,
       'backfilled from run log (batch 2)', timestamptz '2026-07-28 18:00:00+00'
where not exists (
  select 1 from extraction_spend
  where envelope = 'tier3-awarded' and run_url = 'backfilled from run log (batch 2)');
