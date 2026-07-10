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
-- Idempotent: safe to run whether or not the rows were already inserted
-- directly (the 2026-07-10 production hotfix inserted them by hand).
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Department of National Defence — News',
       'https://www.canada.ca/en/department-national-defence.atom.xml',
       'newsroom'::source_type, 'federal'::jurisdiction_level, 'rss', 'daily'
where not exists (select 1 from sources
  where url = 'https://www.canada.ca/en/department-national-defence.atom.xml');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'RCMP — News',
       'https://www.canada.ca/en/royal-canadian-mounted-police.atom.xml',
       'newsroom'::source_type, 'federal'::jurisdiction_level, 'rss', 'daily'
where not exists (select 1 from sources
  where url = 'https://www.canada.ca/en/royal-canadian-mounted-police.atom.xml');

commit;
