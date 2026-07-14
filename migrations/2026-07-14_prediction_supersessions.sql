-- ============================================================================
-- Prediction supersessions: mark a claim as a duplicate/correction/withdrawal
-- of another, WITHOUT breaking immutability and WITHOUT deleting anything.
--
-- Why: a double-submit produced two identical immutable predictions (same
-- procurement, rung, horizon, seconds apart). Both would reconcile and the
-- scorecard would double-count one call, corrupting the hit-rate. Predictions
-- are immutable (a trigger blocks UPDATE/DELETE), so the fix cannot mutate or
-- remove a claim. Instead this append-only table records that one claim
-- supersedes another; the scorecard then excludes the superseded claim, so the
-- pair counts as ONE call while BOTH rows remain visible in the ledger (honest:
-- it shows what actually happened, it does not hide it).
--
-- Semantics stay clean: prediction_outcomes says what happened to the SUBJECT
-- (correct/incorrect/expired); supersessions is a claim-validity relationship
-- (this claim duplicates/corrects/withdraws that one). Append-only, like
-- outcomes and anchors.
--
-- Additive, transactional, idempotent. RLS + grants inline.
-- ============================================================================
begin;

create table if not exists prediction_supersessions (
  id                        uuid primary key default gen_random_uuid(),
  -- the claim being set aside (the duplicate / corrected / withdrawn one)
  prediction_id             uuid not null references predictions(id),
  -- the claim it defers to (the canonical one that stays scored). Null only for
  -- a pure withdrawal with no replacement.
  supersedes_prediction_id  uuid references predictions(id),
  reason                    text not null
                              check (reason in ('duplicate','correction','withdrawn')),
  note                      text,
  created_by                text not null default 'human',
  created_at                timestamptz not null default now(),
  -- a claim is set aside at most once, and never by itself
  unique (prediction_id),
  check (supersedes_prediction_id is null or supersedes_prediction_id <> prediction_id)
);

create index if not exists idx_supersessions_supersedes
  on prediction_supersessions (supersedes_prediction_id)
  where supersedes_prediction_id is not null;

-- Append-only, like outcomes/anchors: a supersession is a historical fact once
-- recorded. A trigger refuses UPDATE and DELETE (defense in depth beyond grants).
create or replace function prediction_supersessions_are_append_only() returns trigger
  language plpgsql as $$
begin
  raise exception 'prediction_supersessions are append-only: % refused', tg_op;
end $$;

drop trigger if exists trg_supersessions_no_change on prediction_supersessions;
create trigger trg_supersessions_no_change before update or delete on prediction_supersessions
  for each row execute function prediction_supersessions_are_append_only();

-- ---- scorecard: exclude superseded claims -----------------------------------
-- Rebuilt identically to 2026-07-13_prediction_ledger.sql, with one added
-- clause: a claim that has been superseded is left out of the scorecard
-- entirely (neither numerator nor denominator), so a duplicate counts as zero
-- additional calls and the canonical claim is the one scored.
create or replace view prediction_scorecard as
with latest as (
  select distinct on (o.prediction_id)
         o.prediction_id, o.outcome, o.resolved_on, o.settling_document_id
    from prediction_outcomes o
   where o.status = 'confirmed'
   order by o.prediction_id, o.created_at desc
)
select
  p.id                        as prediction_id,
  p.made_at,
  p.subject_kind,
  p.gated,
  p.predicted_rung,
  l.outcome,
  l.resolved_on,
  case when d.published_on is not null
       then (d.published_on - p.made_at::date) end as lead_days
from predictions p
join latest l on l.prediction_id = p.id
left join documents d on d.id = l.settling_document_id
where not exists (
  select 1 from prediction_supersessions s where s.prediction_id = p.id
);

-- ---- RLS + grants -----------------------------------------------------------
alter table prediction_supersessions enable row level security;

-- reviewer reads all and INSERTs (marking a duplicate/correction on approval).
-- No update/delete grant, and the trigger blocks them anyway.
drop policy if exists "supersession_read" on prediction_supersessions;
create policy "supersession_read" on prediction_supersessions
  for select to authenticated using (true);
drop policy if exists "supersession_insert" on prediction_supersessions;
create policy "supersession_insert" on prediction_supersessions
  for insert to authenticated with check (true);

grant select, insert on table prediction_supersessions to authenticated;
grant select          on prediction_scorecard          to authenticated;
-- deliberately NO update/delete: append-only, nothing to anon.

commit;
