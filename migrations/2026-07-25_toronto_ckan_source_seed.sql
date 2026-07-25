-- ============================================================================
-- City of Toronto CKAN open-data source seed (docs/toronto-ckan-design.md,
-- 2026-07-25). One row for the collector, URL-keyed insert guard (idempotent,
-- re-runnable), same shape as the MERX/Windsor seed.
--
-- Provenance: ckan0.cf.opendata.inter.prod-toronto.ca is the City of Toronto's
-- own CKAN open-data catalogue (publisher-published by definition). One source
-- row covers all three datasets the collector reads (open solicitations,
-- awarded contracts, non-competitive contracts).
--
-- APPLY AT ENABLEMENT ONLY: the collector's CI validation dry-run runs with
-- dry_run=True and does not require this row. Apply it when the per-dataset
-- VALIDATION table has cleared the 90% bar and the operator approves adding
-- the daily-collect step.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of Toronto Open Data (Toronto Bids)',
       'https://ckan0.cf.opendata.inter.prod-toronto.ca',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://ckan0.cf.opendata.inter.prod-toronto.ca');

commit;
