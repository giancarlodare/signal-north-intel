-- ============================================================================
-- Grants collectors, step 1 of 2: additive doc_type enum values.
--
--   grant_program — a funding program exists / opens (Ontario funding
--                   directory, PS Canada contribution programs)
--   grant_award   — money moved to a recipient (open.canada.ca proactive
--                   disclosure; ingest designed separately)
--
-- Also adds documents.guidelines_gated: some Ontario programs publish their
-- guidelines (the evaluation rubrics) only behind a Transfer Payment Ontario
-- login or by request. Operator rule 2026-07-11: collect the program anyway
-- and record the gate — never skip a program because its guidelines are
-- gated.
--
-- TRANSACTION NOTE: ALTER TYPE ... ADD VALUE runs inside a transaction on
-- PostgreSQL 12+ (Supabase is 15+), but the new labels are NOT usable until
-- that transaction commits. So: run this file alone, in its own SQL editor
-- tab with nothing highlighted, and run 2026-07-11_grants_sources_seed.sql
-- and any collector only AFTER this has committed.
--
-- The enum type is resolved from the documents.doc_type column itself
-- (atttypid::regtype), so the migration cannot mis-guess the type name —
-- the schema predates this repo and we never hardcode names we haven't
-- verified.
--
-- Idempotent: ADD VALUE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS.
-- ============================================================================

do $$
declare
  tname text;
begin
  select atttypid::regtype::text
    into strict tname
    from pg_attribute
   where attrelid = 'public.documents'::regclass
     and attname  = 'doc_type';

  execute format('alter type %s add value if not exists %L', tname, 'grant_program');
  execute format('alter type %s add value if not exists %L', tname, 'grant_award');
end $$;

alter table documents
  add column if not exists guidelines_gated boolean not null default false;

comment on column documents.guidelines_gated is
  'grant_program only: the published guidelines/rubric exist but sit behind '
  'a TPON login or by-request gate, so the program record could not capture '
  'the guideline text. Recorded instead of skipping the program.';
