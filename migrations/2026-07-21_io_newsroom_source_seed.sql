-- ============================================================================
-- Infrastructure Ontario newsroom sources seed (docs/merx-windsor-design.md
-- section 9, approved 2026-07-21). One URL-key-guarded row (idempotent,
-- re-runnable), same shape as the other collector seeds.
--
-- Provenance: infrastructureontario.ca is IO's own site, so award and project
-- announcements are publisher-published by definition. This is the
-- proxy-coverage leg for the parked IO MERX buyer page (section 8): awards
-- via the newsroom are live; the tender feed stays parked pending provenance.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Infrastructure Ontario Newsroom',
       'https://www.infrastructureontario.ca/en/news-and-media/news/',
       'gov_website'::source_type, 'provincial'::jurisdiction_level, 'scraper', 'daily'
where not exists (
  select 1 from sources
   where url = 'https://www.infrastructureontario.ca/en/news-and-media/news/');

commit;
