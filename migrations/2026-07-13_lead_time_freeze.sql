-- ============================================================================
-- Freeze lead-time so the headline metric cannot move after settlement.
--
-- "We called it N days before the market" is the metric Signal North sells, so
-- both ends of the calculation must be immutable:
--   * made_at is already frozen (immutable prediction row, DB-forced now()).
--   * The settling side was NOT: the scorecard read the settling document's
--     published_on LIVE from the mutable documents table, so a later edit to
--     that document could shift a settled claim's lead time.
--
-- Fix: snapshot the settling document's published_on into the outcome row when
-- the settlement is identified (the reconcile job writes it at proposal, the
-- earliest possible moment; the confirm action backfills it for any manually
-- created outcome). The scorecard then reads that FROZEN value, never the live
-- document. With both ends frozen, lead time is fixed at settlement and
-- unforgeable afterward.
--
-- Additive, transactional, idempotent. No prediction row is touched (the new
-- column lives on prediction_outcomes, which is append-only, not immutable).
-- ============================================================================
begin;

alter table prediction_outcomes
  add column if not exists settling_published_on date;

comment on column prediction_outcomes.settling_published_on is
  'The settling document''s event date (published_on) snapshotted at settlement '
  'so lead-time is frozen. The scorecard reads THIS, not the live documents row.';

-- Rewrite the scorecard to read the frozen settling date. Lead time is the
-- days between the claim''s immutable made_at and the frozen settling date;
-- both ends are now fixed at settlement.
create or replace view prediction_scorecard as
with latest as (
  select distinct on (o.prediction_id)
         o.prediction_id, o.outcome, o.resolved_on, o.settling_published_on
    from prediction_outcomes o
   where o.status = 'confirmed'
   order by o.prediction_id, o.created_at desc
)
select
  p.id               as prediction_id,
  p.made_at,
  p.subject_kind,
  p.gated,
  p.predicted_rung,
  l.outcome,
  l.resolved_on,
  case when l.settling_published_on is not null
       then (l.settling_published_on - p.made_at::date) end as lead_days
from predictions p
join latest l on l.prediction_id = p.id;

grant select on prediction_scorecard to authenticated;

commit;
