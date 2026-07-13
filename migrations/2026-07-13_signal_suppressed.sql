-- ============================================================================
-- signals.suppressed: the editorial model's single corpus-membership override.
--
-- Phase 1 of the editorial model redesign (docs/editorial-model-redesign.md).
-- Retires the manual approval gate: a signal is corpus-live the moment it is
-- inserted, and the machine's scores (confidence, evidence_grade, materiality)
-- are the trust layer. The ONLY exclusion from the live corpus is suppression:
--   * a human editor hides a clearly-wrong signal (suppressed_by='human'), or
--   * the triage engine suppresses AR1 noise (suppressed_by='triage@v1').
--
-- Non-destructive and reversible: a suppressed signal stays in the database and
-- in provenance; it is only excluded from the /corpus browser, the procurement
-- proposer, and the weekly brief. Nothing is ever deleted.
--
-- The old columns (reviewed, review_note, reviewed_by) are NOT dropped: they
-- hold historical review/rejection provenance. They simply stop gating anything.
--
-- BACKFILL: every signal a reviewer (or the old triage) already rejected is
-- carried forward as a suppression, so existing exclusions are preserved. Its
-- review_note starts with 'rejected'. Everything else (approved, or never
-- reviewed) becomes live with no action -- that is the whole point.
--
-- GRANTS: the review app's `authenticated` role already holds UPDATE on signals
-- (2026-07-10), so the Phase 3 suppress toggle needs no new grant; the triage
-- engine uses service_role. No new grant here.
--
-- Reviewed, transactional, idempotent (add-column IF NOT EXISTS; the backfill
-- only ever sets suppressed=true on still-false rejected rows, so re-running is
-- a no-op).
-- ============================================================================
begin;

alter table signals add column if not exists suppressed boolean not null default false;
alter table signals add column if not exists suppressed_reason text;  -- 'AR1' | free text
alter table signals add column if not exists suppressed_by text;      -- 'triage@v1' | 'human'

comment on column signals.suppressed is
  'Editorial-model corpus override: true hides the signal from the live corpus '
  '(browser, proposer, brief) without deleting it. Default false = live on '
  'insert; no approval gate. See docs/editorial-model-redesign.md.';

-- Preserve existing rejections as suppressions (human rejects and old AR1
-- auto-rejects alike; both wrote a review_note starting with 'rejected').
update signals
   set suppressed = true,
       suppressed_reason = 'rejected (migrated)',
       suppressed_by = coalesce(reviewed_by, 'human')
 where suppressed = false
   and lower(coalesce(review_note, '')) like 'rejected%';

commit;
