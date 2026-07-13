-- ============================================================================
-- signals.reviewed_by: who cleared a signal off the review queue.
--
-- The review queue previously recorded only WHETHER a signal was reviewed
-- (reviewed bool) and the OUTCOME (review_note = 'approved' / 'rejected: ...').
-- It never recorded WHO did the reviewing. Triage introduces a machine
-- reviewer that auto-approves clean structured-disclosure records, so the
-- record must now distinguish the two hands:
--   * 'triage@v1' -- auto-approved by the rules engine (structured federal
--                   disclosure, confirmed, org-resolved, under the stakes line).
--   * 'human'     -- a person eyeballed it in the review app.
--   * NULL        -- historical rows reviewed before this column existed, or
--                   still unreviewed. We do NOT backfill a guessed reviewer:
--                   "None beats a wrong value." A null here means "unknown who,"
--                   which is the honest state for pre-existing reviews.
--
-- This is the audit spine of the triage/ledger wall: every auto-approval is
-- attributable to the machine and separable from human judgment, so the two
-- can always be filtered apart and the machine can never be mistaken for a
-- person having looked.
--
-- Additive and non-destructive: a nullable column with no default. No existing
-- row changes; the collectors (service_role) are unaffected. The review app's
-- `authenticated` role already holds UPDATE on signals (2026-07-10 grants), so
-- writing this column needs no new grant.
--
-- Reviewed, transactional, idempotent (add-column IF NOT EXISTS is a no-op if
-- the column is already present).
-- ============================================================================
begin;

alter table signals add column if not exists reviewed_by text;

comment on column signals.reviewed_by is
  'Who cleared this signal off the review queue: ''triage@v1'' (rules engine), '
  '''human'' (review app), or NULL (unknown/unreviewed). Set alongside '
  'reviewed=true. Never backfilled with a guess.';

commit;
