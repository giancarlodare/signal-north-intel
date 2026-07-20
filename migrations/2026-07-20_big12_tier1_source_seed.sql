-- ============================================================================
-- Big 12 tier 1 sources seed (docs/big12-tier1-design.md, approved
-- 2026-07-20). One sources row per enabled bids&tenders tenant, URL-keyed
-- insert guards (idempotent, re-runnable), same shape as the Peel seed.
--
-- Every enabled row passed the publisher-linked provenance check; the exact
-- official page is recorded in the design doc. DRPS is HELD (its site does
-- not link the tenant) and is deliberately absent here; add its row in a new
-- migration only after provenance passes.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'York Region Bids and Tenders portal',
       'https://york.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://york.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of London Bids and Tenders portal',
       'https://london.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://london.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Region of Durham Bids and Tenders portal',
       'https://durham.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://durham.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'York Regional Police Bids and Tenders portal',
       'https://yrp.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://yrp.bidsandtenders.ca/Module/Tenders/en');

commit;
