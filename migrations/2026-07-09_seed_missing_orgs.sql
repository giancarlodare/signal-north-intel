-- ============================================================================
-- Insert major Canadian buyers missing from the organizations table.
--
-- An existence check confirmed these 11 do NOT exist (5 federal + 3 more
-- federal + 3 municipal police). PSPC especially matters — largest federal
-- procurement buyer. Aliases are inline for orgs whose short forms are how
-- they're commonly referred; abbreviations that clash with other entities
-- (e.g. "OPS" = Ontario Public Service, "EPS" = Edmonton Public Schools) are
-- deliberately omitted so they can't mis-resolve.
--
-- org_type / jurisdiction use valid enum labels (org_type, jurisdiction_level).
-- province uses 2-letter codes for municipal forces (federal orgs: NULL).
-- Confirmed defaults handle id / created_at / updated_at.
--
-- NOTE: this does NOT touch "Toronto Police Service" or "Toronto Police Service
-- Board" — both already exist and are intentionally separate records (board =
-- early-warning source, service = buyer). Neither this insert nor the alias
-- seed references them.
--
-- Reviewed, additive, transactional, idempotent: WHERE NOT EXISTS on
-- canonical_name means re-running inserts nothing and never overwrites a row.
--
-- Rollback (blocked by the signals FK once referenced — a desirable guard):
--   delete from organizations where canonical_name in ( ...the 11 names... );
-- ============================================================================
begin;

insert into organizations (canonical_name, aliases, org_type, jurisdiction, province, website)
select v.canonical_name, v.aliases, v.org_type::org_type,
       v.jurisdiction::jurisdiction_level, v.province, v.website
from (values
    -- ---- Federal ---------------------------------------------------------
    ('Public Services and Procurement Canada',
        array['PSPC', 'PWGSC', 'Public Services and Procurement Canada',
              'Public Works and Government Services Canada'],
        'federal_department', 'federal', null,
        'https://www.canada.ca/en/public-services-procurement.html'),
    ('Correctional Service of Canada',
        array['CSC', 'Correctional Service of Canada', 'Correctional Service Canada'],
        'corrections', 'federal', null,
        'https://www.canada.ca/en/correctional-service.html'),
    ('Communications Security Establishment',
        array['CSE', 'CSE Canada', 'Communications Security Establishment'],
        'federal_agency', 'federal', null,
        'https://www.cse-cst.gc.ca/en'),
    ('Shared Services Canada',
        array['SSC', 'SSC-SPC', 'Shared Services Canada'],
        'federal_department', 'federal', null,
        'https://www.canada.ca/en/shared-services.html'),
    ('Defence Construction Canada',
        array['DCC', 'Defence Construction Canada'],
        'crown_corp', 'federal', null,
        'https://www.dcc-cdc.gc.ca/'),
    ('Canadian Coast Guard',
        array['CCG', 'Canadian Coast Guard', 'Coast Guard'],
        'federal_agency', 'federal', null,
        'https://www.ccg-gcc.gc.ca/index-eng.html'),
    ('Canadian Security Intelligence Service',
        array['CSIS', 'Canadian Security Intelligence Service'],
        'federal_agency', 'federal', null,
        'https://www.canada.ca/en/security-intelligence-service.html'),
    ('Transport Canada',
        array['Transport Canada', 'TC'],
        'federal_department', 'federal', null,
        'https://tc.canada.ca/en'),
    -- ---- Municipal police (province set) ---------------------------------
    ('Service de police de la Ville de Montréal',
        array['SPVM', 'Service de police de la Ville de Montréal'],
        'police_service', 'municipal', 'QC',
        'https://spvm.qc.ca/'),
    ('Edmonton Police Service',
        array[]::text[],
        'police_service', 'municipal', 'AB',
        'https://www.edmontonpolice.ca/'),
    ('Ottawa Police Service',
        array[]::text[],
        'police_service', 'municipal', 'ON',
        'https://www.ottawapolice.ca/')
) as v(canonical_name, aliases, org_type, jurisdiction, province, website)
where not exists (
    select 1 from organizations o where o.canonical_name = v.canonical_name
);

commit;
