-- ============================================================================
-- Big 12 tier 2 sources seed (docs/tier2-enablement.md, operator go
-- 2026-07-26 after the Sunday brief gate passed). One sources row per
-- enabled bids&tenders tenant, URL-keyed insert guards (idempotent,
-- re-runnable), same shape as the tier-1 seed.
--
-- All nine rows passed the publisher-linked provenance check (7 by machine
-- crawl 2026-07-21, Vaughan and Halton Region by operator browser; evidence
-- in the design doc). Applied at enablement via scripts/apply_tier2_sources.py
-- (same URL-guarded semantics over REST); this file is the durable record.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of Hamilton Bids and Tenders portal',
       'https://hamilton.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://hamilton.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of Brampton Bids and Tenders portal',
       'https://brampton.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://brampton.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of Markham Bids and Tenders portal',
       'https://markham.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://markham.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of Mississauga Bids and Tenders portal',
       'https://mississauga.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://mississauga.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of Kitchener Bids and Tenders portal',
       'https://kitchener.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://kitchener.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Niagara Region Bids and Tenders portal',
       'https://niagararegion.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://niagararegion.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of Vaughan Bids and Tenders portal',
       'https://vaughan.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://vaughan.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Halton Region Bids and Tenders portal',
       'https://haltonregion.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://haltonregion.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Town of Halton Hills Bids and Tenders portal',
       'https://haltonhills.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://haltonhills.bidsandtenders.ca/Module/Tenders/en');

commit;
