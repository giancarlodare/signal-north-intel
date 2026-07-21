-- ============================================================================
-- MERX-Ottawa and Windsor open-data sources seed (docs/merx-windsor-design.md,
-- approved 2026-07-20). One row per collector, URL-keyed insert guards
-- (idempotent, re-runnable), same shape as the tier-1 bids&tenders seed.
--
-- Provenance: opendata.citywindsor.ca is the City of Windsor's own open-data
-- catalogue (publisher-published by definition); merx.com/cityofottawa is
-- linked from ottawa.ca (operator-verified in a human browser 2026-07-20,
-- recorded in the design doc because ottawa.ca's WAF 403s our collector UA).
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of Windsor Open Data Bids and Tenders',
       'https://opendata.citywindsor.ca/Tools/BidsAndTenders',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://opendata.citywindsor.ca/Tools/BidsAndTenders');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of Ottawa MERX solicitations',
       'https://www.merx.com/cityofottawa',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://www.merx.com/cityofottawa');

commit;
