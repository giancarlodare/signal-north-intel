-- ============================================================================
-- Tier-3 sources seed (Phase 1 of the coverage program, operator approved
-- 2026-07-27 under the $500 program cap). One sources row per tenant that
-- CLEARED the CI validation bars in dry-run 30305005716:
--   stcatharines  2/2 ref+date (100%), 463 awarded rows
--   thunderbay    4/4 (100%),          339 awarded rows
--   whitby        5/5 (100%),          685 awarded rows
--   burlington   11/11 (100%),         695 awarded rows
-- HELD below bar, diagnose-and-extend (never enable-and-hope), joining the
-- held pool with markham/niagara/haltonhills/mississauga:
--   niagarafalls  OPEN grid 0 rows (dead-grid shape)
--   sarnia        OPEN grid 0 rows (raised the loud-failure guard)
-- All six passed publisher-linked provenance in the operator's browser
-- 2026-07-26 (docs/tier2-enablement.md). URL-keyed guards; idempotent.
-- Awarded histories stay in the HELD drain pool per the cost gate.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of St. Catharines Bids and Tenders portal',
       'https://stcatharines.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (select 1 from sources
  where url = 'https://stcatharines.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of Thunder Bay Bids and Tenders portal',
       'https://thunderbay.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (select 1 from sources
  where url = 'https://thunderbay.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Town of Whitby Bids and Tenders portal',
       'https://whitby.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (select 1 from sources
  where url = 'https://whitby.bidsandtenders.ca/Module/Tenders/en');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'City of Burlington Bids and Tenders portal',
       'https://burlington.bidsandtenders.ca/Module/Tenders/en',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (select 1 from sources
  where url = 'https://burlington.bidsandtenders.ca/Module/Tenders/en');

commit;
