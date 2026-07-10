-- ============================================================================
-- Seed organization aliases so the extractor resolves common short forms
-- (e.g. "DND" -> Department of National Defence) instead of flagging them for
-- manual resolution.
--
-- Idempotent: appends only aliases not already present (dedupes via distinct),
-- so re-running produces the same result. Matches organizations by a
-- canonical_name ILIKE pattern.
--
-- ⚠️ VERIFY BEFORE RUNNING: the match_pattern values assume these organizations
-- exist with canonical names containing the given text. Adjust the patterns to
-- your actual `organizations.canonical_name` values, and add rows for other key
-- buyers. Rows that match nothing are simply no-ops.
-- ============================================================================
begin;

with seed(match_pattern, new_aliases) as (
    values
        ('%National Defence%',
            array['DND', 'National Defence', 'Department of National Defence']),
        ('%Royal Canadian Mounted Police%',
            array['RCMP', 'Royal Canadian Mounted Police']),
        ('%Public Services and Procurement%',
            array['PSPC', 'PWGSC', 'Public Services and Procurement Canada']),
        ('%Canada Border Services%',
            array['CBSA', 'Canada Border Services Agency']),
        ('%Ontario Provincial Police%',
            array['OPP', 'Ontario Provincial Police']),
        ('%Public Safety Canada%',
            array['Public Safety', 'Public Safety Canada', 'PS Canada']),
        ('%Correctional Service%',
            array['CSC', 'Correctional Service of Canada']),
        ('%Communications Security Establishment%',
            array['CSE', 'Communications Security Establishment']),
        -- Sûreté du Québec already exists; add its short form "SQ" here (not in
        -- the insert). Accents preserved so the ILIKE matches the stored name.
        ('%Sûreté du Québec%',
            array['SQ', 'Sûreté du Québec', 'Surete du Quebec'])
)
update organizations o
set aliases = (
    select array(select distinct a
                 from unnest(o.aliases || s.new_aliases) as a)
)
from seed s
where o.canonical_name ilike s.match_pattern;

commit;
