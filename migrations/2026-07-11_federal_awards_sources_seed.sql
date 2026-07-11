-- ============================================================================
-- Sources rows for the federal grant/contribution AWARDS collector
-- (src/grants_federal_awards.py — design operator-approved 2026-07-11).
-- Requires the grant_award enum value from 2026-07-11_grants_doc_types.sql
-- (already applied).
--
-- All three enum lessons kept:
--   1. Explicit casts on every enum column (bare text 42804s).
--   2. Guards keyed on url (pure ASCII) — em-dashes in names have silently
--      defeated name-keyed guards twice.
--   3. collector uses a REAL collector_method label ('api' — this collector
--      calls the CKAN datastore API, no scraping); module ownership is
--      documented here, not encoded in the enum: all four rows belong to
--      src/grants_federal_awards.py.
--
-- The url is each department's public disclosure search page — the page a
-- human lands on, and the URL-keyed handle the collector resolves its
-- source_id by. Individual award documents carry their own record URLs.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Public Safety Canada — Grant & Contribution Awards',
       'https://search.open.canada.ca/grants/?owner_org=ps-sp',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/grants/?owner_org=ps-sp');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'RCMP — Grant & Contribution Awards',
       'https://search.open.canada.ca/grants/?owner_org=rcmp-grc',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/grants/?owner_org=rcmp-grc');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'National Defence — Grant & Contribution Awards',
       'https://search.open.canada.ca/grants/?owner_org=dnd-mdn',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/grants/?owner_org=dnd-mdn');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Canada Border Services Agency — Grant & Contribution Awards',
       'https://search.open.canada.ca/grants/?owner_org=cbsa-asfc',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/grants/?owner_org=cbsa-asfc');

commit;

-- Verify (expect 4 rows):
--   select name, url, collector, cadence from sources
--   where url like 'https://search.open.canada.ca/grants/%';
