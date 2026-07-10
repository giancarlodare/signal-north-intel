# Signal North — Apply Runbook

The complete, ordered sequence to apply PR #7 (extraction re-architecture) and
PR #8 (review page) against production. Nothing here runs automatically — you
paste each block into the **Supabase SQL Editor** and run it, then run the
extractor, then deploy.

Every SQL block is wrapped in `begin; … commit;`, so each is all-or-nothing: a
failure rolls itself back and leaves the database unchanged.

> Order matters only where noted. Steps 1–4 touch different tables; steps 5–7
> depend on the earlier ones. Run top to bottom.

---

## Step 1 — signals schema  ·  `migrations/2026-07-09_signals_unresolved_org.sql`

Makes `signals.organization_id` nullable and adds `unresolved_org_name` +
`needs_org_resolution`, so the extractor can **store** unresolved signals instead
of dropping them. Required before running the extractor and before PR #8's page.

```sql
begin;
alter table signals alter column organization_id drop not null;
alter table signals add column if not exists unresolved_org_name text;
alter table signals add column if not exists needs_org_resolution boolean not null default false;
commit;
```

**Reversible?** Yes, cleanly — *until* the extractor writes NULL org_ids:
```sql
begin;
alter table signals drop column if exists needs_org_resolution;
alter table signals drop column if exists unresolved_org_name;
alter table signals alter column organization_id set not null;  -- fails once NULLs exist
commit;
```

---

## Step 2 — insert missing buyers  ·  `migrations/2026-07-09_seed_missing_orgs.sql`

An existence check found 12 major buyers absent (9 federal + 3 municipal police).
Insert them first (idempotent via `where not exists`). Does NOT touch the two
Toronto records, which already exist and stay separate. Municipal rows carry a
province code (2-letter).

```sql
begin;
insert into organizations (canonical_name, aliases, org_type, jurisdiction, province, website)
select v.canonical_name, v.aliases, v.org_type::org_type,
       v.jurisdiction::jurisdiction_level, v.province, v.website
from (values
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
    ('Fisheries and Oceans Canada',
        array['DFO', 'Fisheries and Oceans Canada'],
        'federal_department', 'federal', null,
        'https://www.dfo-mpo.gc.ca/index-eng.html'),
    ('Service de police de la Ville de Montréal',
        array['SPVM', 'Service de police de la Ville de Montréal',
              'Service de police de la Ville de Montreal'],
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
```

**Reversible?** Delete the 11 by `canonical_name` (the FK from `signals`
blocks deletion once any signal references them — a desirable guard).

---

## Step 3 — org alias seed  ·  `migrations/2026-07-09_org_aliases_seed.sql`

Run **after** Step 2 (so all the orgs exist). Adds short-form aliases to the
existing federal/provincial buyers — including `SQ` for the already-existing
Sûreté du Québec. A dedupe no-op for aliases already set inline by Step 2.

```sql
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
        ('%Sûreté du Québec%',
            array['SQ', 'Sûreté du Québec', 'Surete du Quebec'])
)
update organizations o
set aliases = (
    select array(select distinct a from unnest(o.aliases || s.new_aliases) as a)
)
from seed s
where o.canonical_name ilike s.match_pattern;
commit;
```

**Reversible?** Additive/low-risk; strip the seeded strings back out if needed
(see PR #7 discussion). Note `'Public Safety'` is a generic alias that could
over-match — drop just that one if it causes mis-resolution.

---

## Step 4 — quarantine Google News  ·  `migrations/2026-07-09_quarantine_google_news_media.sql`

Marks the 1200 provenance-broken `media_article` rows `irrelevant` (kept for
audit, skipped by the extractor). Nothing deleted.

```sql
begin;
update documents
set status = 'irrelevant'
where doc_type = 'media_article'
  and status = 'captured'
  and url ilike '%news.google.com%';
commit;
```

**Reversible?** Fully — set them back to `captured` (same WHERE, flipped status).

---

## Step 5 — data reset (one-time operational cleanup, NOT a repo migration)

These are one-time operations, not schema, so they don't ship as files.

```sql
-- 5a. INSPECT the 26 docs that crashed the OLD extractor (diagnostic only).
select doc_type, count(*), left(error_detail, 100) as sample_error
from documents where status = 'failed'
group by doc_type, left(error_detail, 100);

-- 5b. See what signals exist before deleting (expect ~22, all Manus's stamp).
select extracted_by, count(*) from signals group by extracted_by;
```

```sql
-- 5c. DELETE the disposable signals from the old pipeline, scoped by its stamp
--     (NOT `delete from signals`). They're title-only + mis-provenanced; the new
--     extractor re-creates real ones. Reversible? No — but they're throwaway.
begin;
delete from signals where extracted_by = 'claude-sonnet-4-20250514';
commit;
```

```sql
-- 5d. Un-stick the 26 crashed docs so the new extractor retries them. The crash
--     was in Manus's code, which PR #7 removes, so these will process cleanly.
--     Reversible? Set back to 'failed' — no reason to.
begin;
update documents set status = 'captured', error_detail = null
where status = 'failed';
commit;
```

```sql
-- 5e. OPTIONAL — re-run the 148 already-'extracted' award docs through the new
--     pipeline. LOW YIELD: these are award-notice TITLES; most produce no signal
--     and each still costs an Opus call. RECOMMENDED: skip unless you
--     specifically want corrected-provenance re-extraction of them.
-- begin;
-- update documents set status = 'captured' where status = 'extracted';
-- commit;
```

---

## Step 6 — run the extractor

Runs locally with the three secrets in the environment. The service_role key is
server-side only — never put it in the web app.

```bash
export SUPABASE_URL="https://YOUR-PROJECT.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-sb_secret-key"    # bypasses RLS; server-side only
export ANTHROPIC_API_KEY="your-anthropic-key"
# optional, cheaper for high volume: export EXTRACTION_MODEL="claude-sonnet-5"

pip install -r requirements.txt

# Processes up to batch_size (default 20) per run. Loop until the queue drains:
while true; do
  out=$(python -m src.signal_extractor 2>&1); echo "$out"
  echo "$out" | grep -q "No captured documents" && break
done
```

> Reminder: the remaining `captured` docs are mostly award/tender **titles**,
> which are low-yield for signal extraction (award data already lives structured
> in `contract_awards`). The pipeline earns its keep on richer doc types (news
> releases, board minutes, budgets) once those are collected with real bodies.
> Consider whether to spend Opus tokens on the full award backlog now.

---

## Step 7 — PR #8: review page (RLS → login user → deploy)

1. Apply RLS: `migrations/2026-07-09_signals_rls_review.sql` (⚠️ blast-radius note
   in the file — collector uses service_role and is unaffected).
2. Create your single login user: Supabase → Authentication → Users → Add user.
3. Deploy per `web/README.md` (Vercel: import repo → Root Directory `web` → add
   the two `NEXT_PUBLIC_SUPABASE_*` env vars → Deploy → open on your phone).

Nothing goes public until you say the ethics gate has cleared.
