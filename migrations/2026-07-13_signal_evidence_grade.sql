-- ============================================================================
-- Phase A1: demand-strength taxonomy on every signal.
--
-- Adds an ordinal grade (1..5) answering "is this opportunity real":
--   1 chatter | 2 intent | 3 commitment | 4 in_market | 5 awarded
-- plus the taxonomy-version stamp that produced it, so a later regrade is a
-- new version and a fresh backfill, never an in-place edit of history.
--
-- The grade itself is derived in code (src/taxonomy.py), deterministic and
-- versioned; it is STORED here so the grade is frozen on each signal at write
-- time (the immutable prediction ledger relies on that). This migration only
-- adds the columns and the display reference table. Existing rows are graded
-- by the one-time backfill (src/backfill_evidence_grade.py) after this commits.
--
-- Additive, transactional, idempotent. No collector, workflow, or extraction
-- path is touched. RLS + base grants inline, matching the 2026-07-10 lesson.
-- ============================================================================
begin;

-- ---- signals: the stored grade + its taxonomy version -----------------------
alter table signals
  add column if not exists evidence_grade smallint
    check (evidence_grade between 1 and 5);
alter table signals
  add column if not exists evidence_grade_version text;

comment on column signals.evidence_grade is
  'Demand-strength rung 1..5 (chatter/intent/commitment/in_market/awarded), '
  'derived deterministically by src/taxonomy.py and frozen at write time. '
  'NULL only for rows predating the backfill.';

-- ---- reference table for display + SQL joins --------------------------------
-- Mirrors src/taxonomy.RUNGS. This is DISPLAY metadata, not the grading logic:
-- the mapping that assigns grades lives in versioned code, so editing this
-- table relabels a rung but never silently regrades a signal.
create table if not exists evidence_grade_rungs (
  grade       smallint primary key check (grade between 1 and 5),
  rung        text not null unique,
  description text not null
);

insert into evidence_grade_rungs (grade, rung, description)
select v.grade, v.rung, v.description
from (values
    (1, 'chatter',    'Announcements, opinion, political pressure, media waves. Talk.'),
    (2, 'intent',     'Programs forming, commitments, reforms, funding announced.'),
    (3, 'commitment', 'Budget line, capital plan, board approval, grant award.'),
    (4, 'in_market',  'RFI or pre-RFP, posted tender. A real procurement is live.'),
    (5, 'awarded',    'Contract awarded. Money moved on a procurement.')
) as v(grade, rung, description)
where not exists (select 1 from evidence_grade_rungs e where e.grade = v.grade);

-- ---- RLS + grants (both layers together) ------------------------------------
alter table evidence_grade_rungs enable row level security;

drop policy if exists "rungs_read" on evidence_grade_rungs;
create policy "rungs_read" on evidence_grade_rungs
  for select to authenticated using (true);

grant select on table evidence_grade_rungs to authenticated;
-- read-only reference: no insert/update/delete to authenticated, nothing to
-- anon. service_role (backfill/extractor) bypasses RLS as usual.

commit;

-- After this commits, grade the existing corpus once:
--   python -m src.backfill_evidence_grade --dry-run   # show the distribution
--   python -m src.backfill_evidence_grade             # apply
