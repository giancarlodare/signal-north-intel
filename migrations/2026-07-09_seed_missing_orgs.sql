-- ============================================================================
-- Insert federal buyers missing from the organizations table.
--
-- A pre-check (canonical_name ILIKE the alias-seed patterns) confirmed these
-- three do NOT exist yet, so the alias seed had nothing to attach "PSPC",
-- "CSC", "CSE" to. This inserts them (with aliases inline) so both the seed and
-- the extractor can resolve those names. PSPC especially matters — it's the
-- largest federal procurement buyer.
--
-- org_type / jurisdiction values are valid enum labels (org_type,
-- jurisdiction_level). Required NOT-NULL columns are provided; id / created_at /
-- updated_at rely on the table defaults; province is left NULL (federal).
--
-- Reviewed, additive, transactional, idempotent: WHERE NOT EXISTS on
-- canonical_name means re-running inserts nothing, and it never overwrites an
-- existing row.
--
-- Rollback (safe only while no signal references them — the FK will block
-- otherwise, which is the desired guard):
--   delete from organizations
--   where canonical_name in (
--     'Public Services and Procurement Canada',
--     'Correctional Service of Canada',
--     'Communications Security Establishment');
-- ============================================================================
begin;

insert into organizations (canonical_name, aliases, org_type, jurisdiction, website)
select v.canonical_name, v.aliases, v.org_type::org_type,
       v.jurisdiction::jurisdiction_level, v.website
from (values
    ('Public Services and Procurement Canada',
        array['PSPC', 'PWGSC', 'Public Services and Procurement Canada',
              'Public Works and Government Services Canada'],
        'federal_department', 'federal',
        'https://www.canada.ca/en/public-services-procurement.html'),
    ('Correctional Service of Canada',
        array['CSC', 'Correctional Service of Canada', 'Correctional Service Canada'],
        'corrections', 'federal',
        'https://www.canada.ca/en/correctional-service.html'),
    ('Communications Security Establishment',
        array['CSE', 'CSE Canada', 'Communications Security Establishment'],
        'federal_agency', 'federal',
        'https://www.cse-cst.gc.ca/en')
) as v(canonical_name, aliases, org_type, jurisdiction, website)
where not exists (
    select 1 from organizations o where o.canonical_name = v.canonical_name
);

commit;
