-- ============================================================================
-- Ontario Hansard collector (docs/hansard-design.md, design merged in #104;
-- build 2026-07-26): additive doc_type enum value + URL-guarded sources row.
--
--   legislative_debate: a legislative transcript or committee document
--   (Hansard daily debates, committee estimates). Distinct from news_release
--   so the reader-facing date-type label reads "Legislative statement".
--
-- TRANSACTION NOTE (the 2026-07-11 lesson): ALTER TYPE ... ADD VALUE labels
-- are NOT usable until the transaction commits. Run this file alone, in its
-- own SQL editor tab, before the collector first runs for real. The enum type
-- name is resolved from documents.doc_type itself, never hardcoded.
--
-- APPLY AT ENABLEMENT: the collector's CI validation DRY-RUN writes nothing
-- and needs neither the enum value nor the sources row. Apply when the
-- validation table clears and the operator gives the enablement go.
--
-- Idempotent: ADD VALUE IF NOT EXISTS; URL-guarded insert.
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

  execute format('alter type %s add value if not exists %L', tname, 'legislative_debate');
end $$;

-- Sources row in a separate transaction concern: run after the enum commits.
insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Legislative Assembly of Ontario Hansard',
       'https://www.ola.org/en/legislative-business/house-documents',
       'gov_website'::source_type, 'provincial'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://www.ola.org/en/legislative-business/house-documents');
