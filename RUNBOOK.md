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

> ⚠️ **BLOCKER before the full backlog run: signal-level dedup is not yet
> implemented.** The 10-doc smoke test produced two byte-identical signals from
> two different source documents (same award, "Regional standing offer … O&P
> region"). Nothing in the extractor currently collapses these, so a full-backlog
> run would write twinned signals. Add signal-level dedup (e.g. on
> normalized-title + organization + signal_type, or a content hash) **before**
> draining the queue. The `--limit 10 --dry-run` smoke test is unaffected and
> safe to run now; this blocks only the real drain loop below.

Runs locally with the three secrets in the environment. The service_role key is
server-side only — never put it in the web app.

```bash
export SUPABASE_URL="https://YOUR-PROJECT.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-sb_secret-key"    # bypasses RLS; server-side only
export ANTHROPIC_API_KEY="your-anthropic-key"
# optional, cheaper for high volume: export EXTRACTION_MODEL="claude-sonnet-5"

pip install -r requirements.txt

# SMOKE TEST FIRST (recommended): 10 docs, calls Claude + resolves orgs but
# writes NOTHING. Verifies the API integration, extraction@v1 stamp, and org
# resolution. Safe to run repeatedly.
python -m src.signal_extractor --limit 10 --dry-run

# Real run — processes up to --limit per invocation. Loop until the queue drains:
while true; do
  out=$(python -m src.signal_extractor --limit 20 2>&1); echo "$out"
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
2. Apply the companion grants **immediately after** the RLS migration:
   `migrations/2026-07-10_review_role_grants.sql`. RLS policies sit on top of
   base table GRANTs; without these the review app fails at the privilege layer
   with `permission denied for table signals` before RLS is ever evaluated.
3. Create your single login user: Supabase → Authentication → Users → Add user.
4. Deploy per `web/README.md` (Vercel: import repo → Root Directory `web` → add
   the two `NEXT_PUBLIC_SUPABASE_*` env vars → Deploy → open on your phone).

Nothing goes public until you say the ethics gate has cleared.

---

## Step 8 — grants collectors (Ontario + PS Canada)

Order matters: the enum migration must COMMIT before anything else runs.

1. Apply `migrations/2026-07-11_grants_doc_types.sql` **alone, in its own SQL
   editor tab with nothing highlighted** (adds `grant_program`/`grant_award`
   to the doc_type enum + `documents.guidelines_gated`; new enum labels are
   unusable until this transaction commits — the file's header explains).
2. Apply `migrations/2026-07-11_grants_sources_seed.sql` (three sources rows,
   URL-keyed guards). Verify query at the bottom of the file — expect 3 rows.
3. Dry-run both collectors and eyeball the previews:
   `python -m src.grants_ontario --dry-run` and
   `python -m src.grants_pscanada --dry-run`.
4. One-time closed-archive baseline (after the dry-runs look right):
   `python -m src.grants_ontario --baseline --dry-run`, then without
   `--dry-run`. Never scheduled; safe to re-run (content_hash idempotent).
5. Scheduled runs then need nothing: Ontario open directory rides
   `daily-collect.yml` (same guard/concurrency/healthcheck), PS Canada rides
   `weekly-discovery.yml` Sundays.

Notes: Ontario program deadlines are the event dates (`published_on`);
"ongoing" deadlines and all closed-archive entries are honestly null.
A deadline or status change re-inserts the program as a fresh document —
that's the signal, not a bug. `guidelines_gated=true` marks programs whose
evaluation rubrics sit behind a TPON login / by-request gate (collected, not
skipped).

### Step 8b — federal awards collector (design approved 2026-07-11)

1. Apply `migrations/2026-07-11_federal_awards_sources_seed.sql` (four
   sources rows, URL-keyed guards, `'api'::collector_method`). Verify query
   at the bottom — expect 4 rows.
2. Dry-run and eyeball: `python -m src.grants_federal_awards --dry-run`
   (the CI dry-run also probes the RECORD_URL_TEMPLATE format — that must
   pass before the first real run).
3. Scheduled runs need nothing further: it rides `weekly-discovery.yml`
   after the PS Canada step. open.canada.ca's Crawl-delay of 20s is honored,
   so the first windowed ingest (agreement_start_date ≥ 2024-04-01, capped
   at 25 new docs/dept/run) takes a few minutes and pages through over
   successive Sundays. Amendments insert as fresh documents by design.

---

## Operations — scheduling reliability (standing, not a one-time step)

The daily collector's trigger architecture, alerting, and the one recurring
maintenance task. Context: GitHub's own cron scheduler proved unreliable for
this repo — it dropped scheduled runs on consecutive mornings and delivered
others 6–7 hours late, where the workflow's 6am-ET guard (correctly) skipped
them. The schedule never actually collected until the external trigger was
added.

### Trigger architecture

- **Primary:** cron-job.org fires the `workflow_dispatch` API for
  `daily-collect.yml` at **6:17am America/Toronto** daily (timezone-aware, so
  DST is handled by the scheduler, not by us). The workflow's guard exempts
  `workflow_dispatch`, so a late delivery still does real work. Failure
  notifications (non-2xx response) email from cron-job.org; a successful
  dispatch returns 204.
- **Fallback:** the two GitHub cron entries in `daily-collect.yml`
  (10:17/11:17 UTC ≈ 6:17am EDT/EST) stay in place. Free redundancy on the
  rare day the external trigger hiccups *and* GitHub happens to deliver
  on time.
- **Double-run safety:** inserts are deduped by `content_hash`
  (check-then-insert), and the workflow's `concurrency` group
  (`daily-collect`, `cancel-in-progress: false`) serializes runs, so
  primary + fallback both firing is provably harmless — the second run queues
  behind the first and skips every already-present hash.

### Dead-man's-switch (healthchecks.io) — how the logic works

The workflow pings healthchecks.io **only after a real collection succeeds**
(`should_run == 'true' && success()`). healthchecks.io alerts when it does
NOT receive a ping in time. The timer counts **from the last received ping,
not from a scheduled time**: with **Period = 1 day** and **Grace = 3 hours**,
a miss pages mid-morning (roughly: yesterday's ping time + 24h + 3h).

Every failure mode trips it: no run fired at all → no ping → alert; run fired
but collection errored → `success()` false → no ping → alert; run fired but
guard-skipped → ping step not reached → alert. The trigger source is
irrelevant — the ping happens inside the workflow, so the switch is equally
armed under the external trigger.

The two alert layers catch different failures: **cron-job.org's failure
email** = "couldn't trigger GitHub" (API down, PAT expired — note a 204 only
confirms the dispatch was accepted, not that collection succeeded);
**healthchecks.io** = "triggered but didn't actually collect."

### Healthcheck verification checklist (run after any change to the pipeline)

1. Repo secret `HEALTHCHECK_URL` exists (Settings → Secrets and variables →
   Actions). If missing, the ping step no-ops and the switch is unarmed —
   silence then means *nothing is being monitored*, not "all good".
2. healthchecks.io check: **Period 1 day, Grace 3 hours**.
3. Email integration attached to the check and the address verified.
4. Manually dispatch the workflow once → check flips to "up" (ping received).

### PAT rotation — ⏰ due early October 2026 (90-day expiry)

The cron-job.org job authenticates with a fine-grained GitHub PAT
(`signal-north-collector-dispatch`): **Actions read/write on
signal-north-intel only** (+ mandatory Metadata read), created ~2026-07-10
with 90-day expiry. To rotate:

1. GitHub → Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → generate a new token with the identical scope
   (Only select repositories → signal-north-intel; Actions: Read and write).
2. Update the `Authorization: Bearer …` header in the cron-job.org job.
3. Update the Bitwarden item.
4. Delete the old token in GitHub. Nothing else references it.
5. Wait for the next morning's run (or "Run now" in cron-job.org) and confirm
   a green `workflow_dispatch` run in Actions.

The token lives in **cron-job.org and Bitwarden only** — never in the repo,
never in any chat or transcript.
