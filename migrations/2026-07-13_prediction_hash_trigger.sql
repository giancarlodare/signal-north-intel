-- ============================================================================
-- Predictions: compute made_at AND claim_hash in the DATABASE, not the client.
--
-- Supersedes the insert-time made_at sanity check from the ledger migration.
-- Having the database own both fields is strictly stronger for the "we called
-- it, provably, before date X" guarantee:
--   * made_at is forced to now() at insert, so a claim CANNOT be born
--     backdated at all (stronger than the previous 2-minute window), and no
--     client, dashboard, or service_role code path can set it.
--   * claim_hash is computed by the DB over a canonical serialization of the
--     claim, so the hashing algorithm is single-sourced (no chance of a web
--     client and a Python verifier disagreeing) and the client cannot
--     influence it. src/predictions.claim_hash mirrors this exactly for
--     independent verification.
--
-- The canonical string is ASCII-only by construction (uuids, integers, ISO
-- dates), so it serializes identically everywhere. The evidence hash binds each
-- cited signal's id, grade, document, and event date (its analytical basis);
-- the free-text title/summary stay in evidence_snapshot for the human record
-- but are deliberately not hashed, so unicode serialization can never make the
-- hash ambiguous across languages.
--
-- Safe: the predictions table is empty (no frozen claim exists yet), so
-- installing DB-side hashing now rewrites nothing. pgcrypto provides digest().
-- Idempotent.
-- ============================================================================
begin;

create extension if not exists pgcrypto;

create or replace function predictions_freeze() returns trigger
  language plpgsql as $$
declare
  ev        text;
  canonical text;
begin
  new.made_at := now();   -- authoritative; client value (if any) is ignored

  select coalesce(string_agg(
           (e->>'signal_id') || ',' ||
           coalesce(e->>'evidence_grade', '') || ',' ||
           coalesce(e->>'document_id', '') || ',' ||
           coalesce(e->>'published_on', ''),
           ';' order by e->>'signal_id'), '')
    into ev
    from jsonb_array_elements(new.evidence_snapshot) e;

  canonical :=
       new.subject_kind || '|' ||
       coalesce(new.subject_procurement_id::text, '') || ',' ||
       coalesce(new.subject_organization_id::text, '') || ',' ||
       coalesce(new.subject_category_id::text, '') || '|' ||
       new.predicted_rung::text || '|' ||
       new.horizon_months::text || '|' ||
       ev || '|' ||
       to_char(new.made_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"');

  new.claim_hash := encode(digest(canonical, 'sha256'), 'hex');
  return new;
end $$;

-- Replace the made_at sanity trigger with the freeze trigger (which forces
-- made_at = now() and computes claim_hash). The immutability trigger for
-- UPDATE/DELETE from the ledger migration stays as-is.
drop trigger if exists trg_predictions_made_at on predictions;
drop trigger if exists trg_predictions_freeze on predictions;
create trigger trg_predictions_freeze before insert on predictions
  for each row execute function predictions_freeze();

-- claim_hash is now always set by the trigger; a default keeps a raw insert
-- (should one ever bypass the trigger) from tripping NOT NULL before the
-- trigger runs is unnecessary, but harmless and explicit.
alter table predictions alter column claim_hash set default '';

commit;
