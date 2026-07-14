-- ============================================================================
-- Source seed: Region of Peel bids&tenders portal (municipal tenders + awards).
-- Companion to src/tenders_bidsandtenders.py (docs/peel-tenders-design.md).
--
-- TRANSACTION NOTE: this file is deliberately NOT wrapped in one begin/commit.
-- Postgres forbids USING a newly added enum value in the same transaction that
-- added it, so the `alter type ... add value` must auto-commit before the
-- INSERT references 'municipal'. Applied statement-by-statement (Supabase SQL
-- editor / psql), each top-level statement auto-commits, which is what we want.
--
-- Idempotent: add-value IF NOT EXISTS is a no-op if 'municipal' already exists
-- (the board-minutes municipal sources suggest it does); the INSERT is guarded
-- by a url NOT EXISTS check, so re-running never duplicates.
-- ============================================================================

-- 1. Ensure jurisdiction_level carries 'municipal' (resolved from the column's
--    own type, so we never hardcode the enum name). Auto-commits on its own.
do $$
declare tname text;
begin
  select atttypid::regtype::text
    into strict tname
    from pg_attribute
   where attrelid = 'public.sources'::regclass
     and attname  = 'jurisdiction';
  execute format('alter type %s add value if not exists %L', tname, 'municipal');
end $$;

-- 2. Seed the Peel portal source (runs after the value above is committed).
--    collector 'scraper' = the headless render-and-read path (Method A).
insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Region of Peel Bids and Tenders portal',
       'https://peelregion.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://peelregion.bidsandtenders.ca/Module/Tenders/en');
