-- ============================================================================
-- Sources rows for the federal Contracts proactive-disclosure collector
-- (src/contracts_federal.py). Six public-safety and defence departments, the
-- same set as the grants awards collector.
--
-- All enum lessons kept: explicit casts, url-keyed guards, real
-- collector_method label ('api'; this collector calls the CKAN datastore).
-- The url is each department's public contracts search page, which is also the
-- URL-keyed handle the collector resolves its source_id by. Individual award
-- documents carry their own record URLs.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Public Safety Canada - Contract Awards',
       'https://search.open.canada.ca/contracts/?owner_org=ps-sp',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/contracts/?owner_org=ps-sp');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'RCMP - Contract Awards',
       'https://search.open.canada.ca/contracts/?owner_org=rcmp-grc',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/contracts/?owner_org=rcmp-grc');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'National Defence - Contract Awards',
       'https://search.open.canada.ca/contracts/?owner_org=dnd-mdn',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/contracts/?owner_org=dnd-mdn');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Canada Border Services Agency - Contract Awards',
       'https://search.open.canada.ca/contracts/?owner_org=cbsa-asfc',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/contracts/?owner_org=cbsa-asfc');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Correctional Service Canada - Contract Awards',
       'https://search.open.canada.ca/contracts/?owner_org=csc-scc',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/contracts/?owner_org=csc-scc');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Justice Canada - Contract Awards',
       'https://search.open.canada.ca/contracts/?owner_org=jus',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/contracts/?owner_org=jus');

commit;

-- Verify (expect 6 rows):
--   select name, url from sources
--   where url like 'https://search.open.canada.ca/contracts/%' order by url;
