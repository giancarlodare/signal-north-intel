-- ============================================================================
-- Big 12 board minutes phase 2 sources seed (docs/big12-boards-design.md,
-- approved 2026-07-20). One sources row per enabled board, URL-keyed insert
-- guards (idempotent, re-runnable), same shape as the tier-1 tenders seed.
--
-- Every enabled row passed the publisher-linked provenance check in the
-- four-pass CI probe. Parked boards (Hamilton, Niagara, London, Windsor,
-- Ottawa) are deliberately absent; their rows arrive with their unparking
-- migrations only after the recorded verdicts are resolved.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'York Regional Police Services Board - Meetings',
       'https://www.yrpsb.ca/meetings',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources where url = 'https://www.yrpsb.ca/meetings');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Durham Regional Police Services Board - Meetings',
       'https://durhampoliceboard.ca/archived-board-meetings-agendas-and-minutes/',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://durhampoliceboard.ca/archived-board-meetings-agendas-and-minutes/');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Halton Police Board - Meetings',
       'https://haltonpoliceboard.ca/meetings/',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources where url = 'https://haltonpoliceboard.ca/meetings/');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Waterloo Regional Police Services Board - Meetings',
       'https://www.wrps.on.ca/police-service-board-meetings',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://www.wrps.on.ca/police-service-board-meetings');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Greater Sudbury Police Services Board - Meetings',
       'https://www.gsps.ca/about-gsps/greater-sudbury-police-service-board/board-meetings/',
       'gov_website'::source_type, 'municipal'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://www.gsps.ca/about-gsps/greater-sudbury-police-service-board/board-meetings/');

commit;
