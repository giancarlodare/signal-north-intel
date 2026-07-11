-- ============================================================================
-- Defence Investment Agency — News: sources row.
--
-- Operator-approved 2026-07-11 as the manual version of a discovery approval:
-- a government newsroom on canada.ca, provenance-clean, and currently where
-- procurement-grade defence content publishes (Canadian Patrol Submarine
-- Project advances). Feed CI-probe-verified: the GC News Centre API returns
-- 10 entries for dept=defenceinvestmentagency.
--
-- Idempotent via URL-keyed guard (ASCII, immune to the em-dash name issue).
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Defence Investment Agency — News',
       'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=defenceinvestmentagency&sort=publishedDate&orderBy=desc&pick=50&format=atom&atomtitle=Defence%20Investment%20Agency',
       'newsroom'::source_type, 'federal'::jurisdiction_level, 'rss', 'daily'
where not exists (select 1 from sources
  where url like '%dept=defenceinvestmentagency%');

commit;
