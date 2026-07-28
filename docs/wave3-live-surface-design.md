# Wave 3 next stage: the live member surface (closing soon)

Status: DESIGN for operator review. Nothing builds until the operator
approves the decision points; nothing goes member-visible without the
staged-dark flag discipline and a validation dry-run table.

Operator directive (2026-07-28): with the corpus at 15 buyers and ~85
tenders/day, a member seeing only the weekly brief is too thin. Members
should feel the live intelligence stream between issues -- fail-safe, a
defined corpus slice with its own RLS universe, same client-facing-gate
discipline as everything else.

## What members get

A "Closing soon" surface: live public-safety-relevant tender and grant
opportunities with a future deadline, newest-closing-first, each carrying
buyer, deadline (date-type-label rules; never a fabricated day), reference
number, category, and the honest provenance link (record/listing/portal
labels per web/lib/portal/provenance.ts). Placement: its own /portal page
plus a short rail on Home. Read-only in v1: no per-item actions beyond the
provenance link (saving stays brief-scoped until decided otherwise).

## The safe RLS-widening shape (the decision that matters)

We do NOT widen the member policies on `signals`/`documents`. Those tables
carry operator-internal state (grades, review stamps, suppression,
unresolved orgs), and every widening of a policy on a rich table is a new
leak surface. Instead, the house pattern already trusted for demand-arc and
watches:

**A purpose-built projection table, `member_live_items`, written by a
deterministic daily job.** The database cannot leak what the table does not
contain.

* Writer: `src/live_surface.py --apply` (service role, daily-collect step,
  no LLM). Deletes-and-rewrites the projection each run (small: tens to a
  few hundred rows).
* Slice definition (v1, every condition fail-closed):
  - signal `public_safety is true` (the tested member barrier; fail-closed
    NULL never passes)
  - `suppressed_by is null`
  - doc_type in (`tender_notice`, `grant_program`)
  - document `published_on` (the closing/deadline date) in
    [today, today + 30] (grants + 45, matching the brief's lead windows)
  - evidence grade >= 4 (in-market or better; keeps board chatter off a
    surface named "closing soon")
* Projected columns only: headline, buyer name, closing_on,
  date_precision, doc_type, reference_number, url, category_slug,
  defence_relevant, signal_id (for watch linkage), refreshed_at. NO
  grades, NO review state, NO amounts in v1 (amounts can join later as a
  deliberate decision).
* RLS on the projection: enable RLS; `sn_member_read using (true)` for
  authenticated PLUS the standard restrictive write clamps
  (operator/service-role only). Simple policies on a table that only ever
  contains gate-cleared rows -- the gate lives in the writer, reviewed as
  code, unit-tested, and auditable in one file.
* The existing member policies on signals/documents/briefs are UNTOUCHED.
  Rollback is `drop table` + remove the page; no policy surgery.

Why this is safer than widening signals RLS: (1) one reviewable gate
instead of policy predicates spread across tables; (2) no risk of a new
permissive policy OR-ing past an existing clamp; (3) the projection can be
emptied instantly (kill switch) without touching the corpus; (4) the page
queries one flat table -- no embed chains, no cross-table RLS interactions
(the class of bug that produced today's 0-items incident).

## Freshness, honesty, loud failure

* Refreshed by daily-collect after the collectors run; `refreshed_at`
  renders on the page ("as of 6:47 a.m. Eastern") so freshness is a claim
  the page proves, not implies.
* The writer raises loudly on zero candidate rows (with the corpus at ~85
  tenders/day, an empty slice means a broken join, never a quiet truth).
* Deadlines render under the standing date rules; a month-precision date
  never fabricates a day.

## Watch linkage (follow-on decision, not v1)

Once the projection exists, the watch matcher CAN also match against it
(live alerts between issues). That changes the matcher's universe --
decision A (2026-07-27) currently scopes it to brief-published items -- so
it ships only as its own operator decision, not silently with this build.

## Validation bars before enablement

Dry-run table to the operator: projected row count, per-buyer and per-type
distribution, deadline-parse rate (must be 100% of projected rows by
construction), 10 sample rows with provenance labels, and confirmation the
projection contains zero rows failing any slice condition (asserted by the
writer, not eyeballed). Then operator go; page ships behind PORTAL_ENABLED
exactly like every member surface (preview first, production dark).

## Decision points for the operator

* D1 projection-table pattern vs widening signals RLS (recommended:
  projection, above).
* D2 slice: grade >= 4 + public_safety + unsuppressed + 30/45-day windows
  (recommended); anything looser is a deliberate later widening.
* D3 v1 excludes amounts and any operator-internal fields (recommended).
* D4 watch-matcher live linkage deferred to its own decision (recommended).
