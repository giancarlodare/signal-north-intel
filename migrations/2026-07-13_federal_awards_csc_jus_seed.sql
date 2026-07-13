-- ============================================================================
-- Two more federal awards departments: Correctional Service Canada (csc-scc)
-- and Justice Canada (jus). More awarded-rung disclosure for the prediction
-- spine (operator, 2026-07-13). Same collector (src/grants_federal_awards.py),
-- one config line each plus these two sources rows.
--
-- owner_org codes CI-probe-verified against the open.canada.ca datastore
-- before this migration was written (the verify-don't-guess rule). Requires
-- the grant_award enum value (2026-07-11_grants_doc_types.sql, applied).
--
-- All enum lessons kept: explicit casts, url-keyed guards, real
-- collector_method label ('api'; this collector calls the CKAN datastore).
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Correctional Service Canada - Grant & Contribution Awards',
       'https://search.open.canada.ca/grants/?owner_org=csc-scc',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/grants/?owner_org=csc-scc');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Justice Canada - Grant & Contribution Awards',
       'https://search.open.canada.ca/grants/?owner_org=jus',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'api'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://search.open.canada.ca/grants/?owner_org=jus');

commit;

-- Verify (expect 6 federal-awards rows total after this):
--   select name, url from sources
--   where url like 'https://search.open.canada.ca/grants/%' order by url;
