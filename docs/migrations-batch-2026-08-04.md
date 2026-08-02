# Aug 4 migrations batch — one paste sitting (enumerated 2026-08-03)

Every schema change the fortnight needs, collected so the Aug 4 paste is a
single sitting rather than a per-day interruption (operator directive). All
are `add column if not exists` / additive-and-guarded; none drops or
rewrites. Verify with `scripts/verify_pastes.py` after, as with prior sets.

Order does not matter between these (no cross-dependencies). The relevance
column already shipped (2026-08-02, pasted); it is NOT repeated here.

## 1. closes_on — the actionable deadline, extracted (task #56 sibling)

The imminent window keys on `published_on` as a proxy deadline. A real
`closes_on` lets the scorer's window curve act on the true closing date and
feeds precedent matching. Nullable; the extractor populates it, NULL means
unknown (never a fabricated date).

```sql
alter table documents add column if not exists closes_on date;
comment on column documents.closes_on is
  'True closing/deadline date when extracted; NULL = unknown (never fabricated). 2026-08-04.';
```

## 2. Categorization columns — pending the categorization design doc

The categorization design doc (reaches the operator Aug 5 eve / Aug 6 morn)
will confirm the exact set. The columns it is expected to need, staged here
so they ride this one paste rather than forcing a second mid-week paste:

```sql
-- notice_kind: the ACAN/RFI/LOI distinction collapsed at src/main.py:189
-- (all became tender_notice); recover it as a categorization, not by
-- un-collapsing collection.
alter table documents add column if not exists notice_kind text;
comment on column documents.notice_kind is
  'ACAN/RFI/LOI/tender sub-type recovered from content; NULL = plain tender_notice. 2026-08-04.';

-- buyer_type: real buyer typing (the PSPC string-collision worked example);
-- distinguishes a true civil buyer from a public-safety one downstream.
alter table documents add column if not exists buyer_type text;
comment on column documents.buyer_type is
  'Resolved buyer class for downstream relevance (e.g. civil vs public-safety). 2026-08-04.';
```

GATED NOTE: if the categorization design doc lands with a different column
set, the unused staged columns stay harmless (nullable, unread) and the doc
adds only what it additionally needs. Pasting these two early costs nothing
and removes a mid-week blocker.

## 3. brief_issue anchor support — already satisfied, no migration

The issue-anchored recent window (shipped 2026-08-02) reads
`briefs.status='published'` and `briefs.week_start`, both of which already
exist. No column needed; noted here so it is not mistaken for a gap.

## Not in this batch (deliberately)

* **Standing-programs surfacing** (the 89 undated grant programs): a
  product-shape ruling first, THEN its schema. Waits for the operator's
  standing-programs decision (this evening's DECISION digest); its column,
  if any, rides a later paste, not this one.
* **Anything member-facing or spend-touching**: gated class, unchanged.
