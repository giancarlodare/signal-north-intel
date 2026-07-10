-- ============================================================================
-- Sources rows for the two newsroom feeds the rebuilt RSS collector adds
-- (DND, RCMP). Ontario Newsroom and Public Safety Canada rows already exist.
--
-- Idempotent: where-not-exists on name.
--
-- FIXED 2026-07-10: the original used a `(values …) as v` subselect, whose
-- literals are typed text — Postgres refuses the implicit text→enum insert
-- (42804: column "source_type" is of type source_type but expression is of
-- type text). Rewritten as per-row insert…select with explicit enum casts,
-- same style as the org seed migration.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Department of National Defence — News',
       'https://www.canada.ca/en/department-national-defence.atom.xml',
       'newsroom'::source_type, 'federal'::jurisdiction_level, 'rss', 'daily'
where not exists (select 1 from sources
                  where name = 'Department of National Defence — News');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'RCMP — News',
       'https://www.canada.ca/en/royal-canadian-mounted-police.atom.xml',
       'newsroom'::source_type, 'federal'::jurisdiction_level, 'rss', 'daily'
where not exists (select 1 from sources where name = 'RCMP — News');

commit;
