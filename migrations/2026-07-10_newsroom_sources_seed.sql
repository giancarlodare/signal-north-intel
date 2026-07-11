-- ============================================================================
-- Sources rows for the two newsroom feeds the rebuilt RSS collector adds
-- (DND, RCMP). Ontario Newsroom and Public Safety Canada rows already exist.
--
-- FIXED twice, both lessons kept:
--   1. 42804 text→enum: a `(values …) as v` subselect types literals as text
--      and Postgres refuses the implicit enum insert. Fixed with per-row
--      insert…select and explicit ::source_type / ::jurisdiction_level casts.
--   2. Silent no-op: the idempotency guard originally keyed on `name`, which
--      contains an em-dash — one dash/encoding variant anywhere (row or SQL)
--      and the guard mismatches invisibly. Now keyed on `url`, which is pure
--      ASCII and stable, so the guard can never be defeated by typography.
--
-- FEED URLS corrected 2026-07-11: the canada.ca/en/<dept>.atom.xml pattern
-- returns an HTML Not Found page with HTTP 200 (broke the first live run);
-- the Canada News Centre API atom URLs below are CI-probe-verified real feeds.
--
-- Idempotent: safe to run whether or not the rows were already inserted
-- directly (the 2026-07-10 production hotfix inserted them by hand).
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Department of National Defence — News',
       'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentofnationaldefence&sort=publishedDate&orderBy=desc&pick=50&format=atom&atomtitle=National%20Defence',
       'newsroom'::source_type, 'federal'::jurisdiction_level, 'rss', 'daily'
where not exists (select 1 from sources
  where url = 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentofnationaldefence&sort=publishedDate&orderBy=desc&pick=50&format=atom&atomtitle=National%20Defence');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'RCMP — News',
       'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=royalcanadianmountedpolice&sort=publishedDate&orderBy=desc&pick=50&format=atom&atomtitle=RCMP',
       'newsroom'::source_type, 'federal'::jurisdiction_level, 'rss', 'daily'
where not exists (select 1 from sources
  where url = 'https://api.io.canada.ca/io-server/gc/news/en/v2?dept=royalcanadianmountedpolice&sort=publishedDate&orderBy=desc&pick=50&format=atom&atomtitle=RCMP');

commit;
