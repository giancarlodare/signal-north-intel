# Discovery Engine — Design (propose-then-approve)

**Status: DESIGN FOR REVIEW — no code exists yet.** Nothing below gets built
until this document is approved. Rebuilt from the concept in the parked
`schema_patch_v13_autonomous.sql`, discarding its implementation.

## 1. Purpose

A weekly job that reads the recent corpus and **proposes — never acts**:

1. **New sources** — domains/newsrooms/boards repeatedly referenced in
   collected documents that we don't collect from.
2. **New entities** — organizations, senior appointments (e.g. a new
   association president), companies signaling Canadian investment intent —
   recurring above a threshold.
3. **Alias/org updates** — e.g. a ministry renamed after a cabinet shuffle.

Proposals land in two new tables and surface on a third web-app page
(Discovery, next to Review and Prospects) with one-tap approve/reject.

## 2. Hard rules (non-negotiable, enforced structurally)

- **Propose-only.** The weekly job's write surface is exactly the two
  `discovered_*` tables. It never inserts into `sources` or `organizations`,
  never modifies a collector, never schedules anything.
- **No source runs until approved.** Approval creates the `sources` row;
  *wiring a collector to it remains a separate reviewed PR* (collectors are
  hardcoded configuration by design — see §6).
- **No outbound fetches to candidate domains.** Discovery reads only what the
  collectors already stored. It never crawls a proposed source to "check it
  out" — that would be collection before approval.
- **Provenance absolute.** Every proposal carries the document IDs it was
  derived from; the Discovery page renders them as links to the publisher
  URLs. A proposal with no evidence documents cannot exist (NOT NULL + check).
- **Nothing public-facing, no social media.** Social/aggregator domains are
  structurally excluded by a blocklist (§4.1) and never proposed.

## 3. Inputs (all already in the database)

| Input | Used for |
|---|---|
| `documents` from the last 90 days, incl. `content` bodies (board minutes, news releases) | domain-frequency scan; LLM entity pass |
| `signals.unresolved_org_name` where `needs_org_resolution` | recurring-entity candidates (already human-meaningful and free) |
| `sources.url` | "already collected" exclusion set |
| `organizations.canonical_name/aliases` | alias-update matching; "already known" exclusion |
| `contract_awards.vendor_name` | company-recurrence corroboration |

## 4. Detection

### 4.1 New sources — pure SQL/Python heuristic, no LLM

Extract absolute URLs from recent `documents.content` bodies, reduce to
registrable domain, count **distinct referencing documents** per domain.
Propose when:

- distinct-document count ≥ **3** in the window, and
- domain not in the exclusion set (domains of existing `sources` rows,
  domains already proposed/rejected, and the **blocklist**: social media,
  Google News/aggregators, URL shorteners, ad/tracking domains), and
- domain looks like a publisher (heuristic: `.ca`/`.gc.ca`/`.gov.*`/known
  board/municipal patterns rank first; everything else still proposable,
  ranked lower).

`kind` is guessed (`newsroom` / `board` / `association` / `publisher_other`)
from URL path hints (e.g. `/meetings`, `/newsroom`, `/rss`) — a label for the
reviewer, not a decision.

### 4.2 New entities — unresolved-org counts first, LLM second

**Tier 1 (free, deterministic):** group `signals.unresolved_org_name`
(normalized with the extractor's accent/case folding) with count ≥ **2** →
propose `entity_kind='organization'`, prefilled with the raw name and the
evidence signal/doc IDs. This is the highest-precision signal we have: the
extractor already said "I found an org I couldn't resolve."

**Tier 2 (LLM, capped):** a versioned prompt — `prompts/discovery/v1.txt`,
stamped `discovery@v1` in `proposed_by`, same library/changelog discipline as
extraction — runs over the window's **rich-bodied** documents only (board
minutes, full news releases), capped at **50 docs/week**, model
`claude-haiku-4-5` (cheap; this is candidate generation, not judgment — the
human is the judgment). Structured output constrained to:
`person_appointment` (name, role, org), `company_canada_intent`
(company, what signaled intent), `organization` (missed by tier 1).
Candidates are merged by normalized name; anything below **2 distinct
evidence documents** is discarded, not proposed.

### 4.3 Alias/org updates

When a tier-1/tier-2 organization candidate is a near-match to an existing
`organizations` row (same normalized name modulo a
ministry/department-style prefix/suffix change, e.g. "Ministry of the
Solicitor General" → "Ministry of Public and Business Service Delivery"
style renames), propose `entity_kind='alias_update'` carrying
`existing_organization_id` + the new name — so approval is "add alias to the
org we already track," not a duplicate org.

## 5. Data model (what the v13 patch got wrong, fixed)

The v13 patch's tables auto-inserted into live tables and its reporting views
cross-joined unfiltered (Cartesian). This rebuild: **transactional,
idempotent, no views at all** (the web page queries the tables directly),
RLS + base grants in the same file (the 2026-07-10 lesson), no DELETE grant.

```sql
-- migrations/2026-07-XX_discovery_tables.sql  (sketch — final DDL with the build)
begin;

create table if not exists discovered_sources (
  id                uuid primary key default gen_random_uuid(),
  domain            text not null unique,          -- idempotency key
  suggested_name    text not null,
  kind              text not null default 'publisher_other'
                    check (kind in ('newsroom','board','association','publisher_other')),
  sample_urls       text[] not null,               -- up to 5 real publisher URLs seen
  evidence_document_ids uuid[] not null check (array_length(evidence_document_ids,1) >= 1),
  mention_count     integer not null default 1,
  first_seen_on     date not null default current_date,
  last_seen_on      date not null default current_date,
  proposed_by       text not null,                 -- 'heuristic@v1'
  status            text not null default 'proposed'
                    check (status in ('proposed','approved','rejected')),
  review_note       text,
  reviewed_at       timestamptz,
  created_source_id uuid references sources(id),   -- set on approval
  created_at        timestamptz not null default now()
);

create table if not exists discovered_entities (
  id                uuid primary key default gen_random_uuid(),
  entity_kind       text not null check (entity_kind in
                    ('organization','person_appointment','company_canada_intent','alias_update')),
  name              text not null,
  normalized_name   text not null,                 -- accent/case-folded; part of the idempotency key
  detail            jsonb not null default '{}',   -- role/org for people, intent summary for companies
  existing_organization_id uuid references organizations(id),  -- alias_update target
  evidence_document_ids uuid[] not null check (array_length(evidence_document_ids,1) >= 1),
  mention_count     integer not null default 1,
  proposed_by       text not null,                 -- 'unresolved-orgs@v1' | 'discovery@v1'
  status            text not null default 'proposed'
                    check (status in ('proposed','approved','rejected')),
  review_note       text,
  reviewed_at       timestamptz,
  created_at        timestamptz not null default now(),
  unique (entity_kind, normalized_name)            -- idempotency key
);

-- RLS + grants in the same file: authenticated select/update, NO insert
-- (only the weekly job's service_role writes proposals), NO delete, anon nothing.
commit;
```

**Idempotency:** the weekly job upserts on the unique keys
(`on conflict … do update`) to bump `mention_count`, extend
`last_seen_on`, and merge evidence — **except** it never touches rows whose
status is `approved` or `rejected`. A rejection is permanent suppression:
re-detection of a rejected domain/entity is a silent count bump on the
rejected row, never a re-proposal.

## 6. Approval flow (web app, `/discovery`)

Third page next to Review and Prospects; same auth gate, noindex, RLS
posture, deliberate-button pattern, **no delete anywhere**.

- **List view:** proposed items, sources and entities in two sections,
  ordered by `mention_count` desc. Each card: name/domain, kind badge,
  count, first/last seen, and the **evidence links** (publisher URLs).
- **Approve a source** → server action inserts the `sources` row
  (name/url/kind mapped; `last_collected_at` null) and stamps
  `created_source_id` + `status='approved'`. The row is *ready for its
  collector* — but no collector reads it until a reviewed PR adds the feed/
  board to the relevant collector's configuration. The page shows approved-
  but-unwired sources as a reminder queue.
- **Approve an entity** (`organization`) → server action inserts into
  `organizations` (canonical_name = name; org_type/jurisdiction from two
  small selects on the card, defaulted from `detail`).
  (`alias_update`) → appends the new alias to
  `organizations.aliases` on `existing_organization_id` (deduped, same
  array-distinct pattern as the alias seed migration).
  (`person_appointment` / `company_canada_intent`) → approval just marks
  reviewed; these are intelligence for you (and Prospects fodder), not rows
  in `organizations`. A "send to prospects" enhancement can come later.
- **Reject** → `status='rejected'` + optional note. Kept forever as
  suppression + audit.

All approve actions are enum-validated server-side and write through the
authenticated role's RLS/grants (select/update on `discovered_*`, insert on
`sources`, insert/update on `organizations` — the grants ship in the same
migration, scoped to exactly these operations).

## 7. Job mechanics

- **Separate workflow** `weekly-discovery.yml`: cron Sundays ~07:17 ET
  (same dual-UTC + guard pattern), `workflow_dispatch` for manual runs,
  its own concurrency group, **no healthcheck ping** (a missed discovery week
  is not an incident) — but a failed run still fails visibly in Actions.
- `python -m src.discovery --dry-run` prints every proposal it *would*
  upsert, writing nothing — same verification discipline as the collectors.
- Runtime budget: tier 1 is one SQL round-trip; tier 2 ≤ 50 Haiku calls.

## 8. Open questions for your review

1. **Thresholds** — domain ≥3 distinct docs, entity ≥2: right starting
   points? (Both are constants, trivially tunable.)
2. **Tier-2 model** — Haiku proposed for cost; Sonnet if you want richer
   `detail` summaries on appointment/intent candidates.
3. **Window** — 90 days rolling, or since-last-run?
4. **`company_canada_intent` → Prospects** — worth wiring "approve into
   prospects table" in v1, or keep approval as mark-reviewed-only first?
   (Design assumes mark-reviewed-only.)
5. **Blocklist location** — code constant (versioned, PR-reviewed) vs table
   (editable without deploy). Design assumes **code constant**, consistent
   with "sources are configuration."

## 9. Build plan once approved (three commits, one PR)

1. Migration (tables + RLS/grants) + `prompts/discovery/v1.txt` + changelog.
2. `src/discovery.py` (tier 1 + tier 2 + upsert; `--dry-run`) + tests
   (thresholds, blocklist, idempotent re-run, rejected-stays-rejected,
   dry-run zero-write) + `weekly-discovery.yml`.
3. `web/app/discovery/` (list + approve/reject server actions) mirroring the
   Prospects patterns.
