-- ============================================================================
-- Add 'captured_construction' to the documents.status enum (processing_status).
-- (operator-approved 2026-08-06, fixing the daily-collect outage.)
--
-- WHY: the Corridor civil-works holdback (src/filters.py document_status())
-- writes status='captured_construction' for construction-only docs, so they
-- are stored but held OUT of the daily extraction pass until Corridor gets its
-- own envelope. That code shipped believing documents.status was unconstrained
-- text (it is NOT -- it is the processing_status enum), so every run that
-- captured a construction-classified tender/award doc failed the insert with
-- Postgres 22P02 and took the whole collector run down. This migration adds the
-- missing enum label; collection recovers on the next daily-collect run (the
-- collector is content-hash idempotent, so the held-off docs are re-collected,
-- no permanent loss).
--
-- TRANSACTION NOTE (the 2026-07-11 lesson): ALTER TYPE ... ADD VALUE labels are
-- NOT usable until the transaction commits. Run this file ALONE, in its own SQL
-- editor tab. The enum type name is resolved from documents.status itself,
-- never hardcoded. Idempotent: ADD VALUE IF NOT EXISTS.
-- ============================================================================

do $$
declare
  tname text;
begin
  select atttypid::regtype::text
    into strict tname
    from pg_attribute
   where attrelid = 'public.documents'::regclass
     and attname  = 'status';

  execute format('alter type %s add value if not exists %L', tname, 'captured_construction');
end $$;
