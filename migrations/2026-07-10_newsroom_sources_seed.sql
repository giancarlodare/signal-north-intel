-- ============================================================================
-- Sources rows for the two newsroom feeds the rebuilt RSS collector adds
-- (DND, RCMP). Ontario Newsroom and Public Safety Canada rows already exist.
--
-- Idempotent: where-not-exists on name. If your sources table's column list
-- differs (it predates the repo), adjust the column names here — the
-- collector itself resolves rows by NAME (or the *_SOURCE_ID env vars), so
-- only the names below must match what gets inserted.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select v.name, v.url, v.source_type, v.jurisdiction, v.collector, v.cadence
from (values
    ('Department of National Defence — News',
     'https://www.canada.ca/en/department-national-defence.atom.xml',
     'newsroom', 'federal', 'rss', 'daily'),
    ('RCMP — News',
     'https://www.canada.ca/en/royal-canadian-mounted-police.atom.xml',
     'newsroom', 'federal', 'rss', 'daily')
) as v(name, url, source_type, jurisdiction, collector, cadence)
where not exists (select 1 from sources s where s.name = v.name);

commit;
