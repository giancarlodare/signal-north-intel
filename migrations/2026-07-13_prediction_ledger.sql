-- ============================================================================
-- Phase B: the prediction and track-record ledger (the core asset).
--
-- Every prediction is an immutable, time-stamped, falsifiable claim: "the
-- subject will reach demand rung R within N months, on this public evidence."
-- Later, reconciliation records what actually happened, and a running hit-rate
-- plus lead-time (how far ahead of the market the call was) is computed from
-- confirmed outcomes.
--
-- Design + operator decisions (docs/prediction-ledger-design.md, 2026-07-13):
--   * IMMUTABLE claims. A prediction is frozen at insert. No update, no delete,
--     ever (enforced by a trigger AND withheld grants). Corrections are new
--     rows. Reconciliation lives in a SEPARATE table so the claim never
--     changes.
--   * PUBLIC provenance, structural. evidence_signal_ids is NOT NULL with an
--     array-length check, so a claim cannot exist without linked evidence
--     (each signal ties to a document with a publisher URL). This inherits the
--     government-capacity firewall: a claim can rest only on public record.
--   * HUMAN-AUTHORED on approval (Q1). Only a human approving inserts a row;
--     the engine proposes candidates in the UI, never writes a prediction.
--   * SUBJECT is procurement-level OR company-level (Q2). Company-level
--     (organization_category) claims are gated behind the investor seam:
--     logged and reconciled from day one so the track record starts, but never
--     surfaced to sellers. `gated` marks them.
--   * PREDICTED RUNG must be commitment or higher (Q4): a claim predicts the
--     subject reaches a strong, public rung (3..5). Chatter/intent can never
--     be a predicted outcome, and a press release can never settle a claim.
--   * HORIZON is explicit and expires exactly at horizon end (Q3), no grace.
--     The default varies by the subject's current rung (set in code); the
--     column just stores whatever the human chose.
--   * CLAIM HASH: a tamper-evident sha256 over the claim's fields, computed in
--     code and stored, so a later edit by anyone with DB access is detectable.
--
-- Additive, transactional, idempotent. RLS + grants inline. No collector,
-- workflow, or extraction path touched.
-- ============================================================================
begin;

-- ---- predictions (immutable) ------------------------------------------------
create table if not exists predictions (
  id                       uuid primary key default gen_random_uuid(),
  made_at                  timestamptz not null default now(),   -- authoritative timestamp
  made_by                  text not null default 'ledger@v1',
  subject_kind             text not null
                             check (subject_kind in ('procurement','organization_category')),
  subject_procurement_id   uuid references procurements(id),
  subject_organization_id  uuid references organizations(id),
  subject_category_id      uuid references categories(id),
  predicted_rung           smallint not null check (predicted_rung between 3 and 5),
  horizon_months           smallint not null check (horizon_months > 0),
  horizon_ends_on          date not null,
  rationale                text not null,
  evidence_signal_ids      uuid[] not null
                             check (array_length(evidence_signal_ids, 1) >= 1),
  -- The evidence CONTENT frozen at claim time, not just the ids. Each element
  -- captures a cited signal's material state (grade, title, summary, document
  -- url, event date) as it was when the claim was made, so a later edit to a
  -- signal can never retroactively alter what the claim was based on. The
  -- claim_hash covers this snapshot, so tampering with the frozen evidence is
  -- detectable too.
  evidence_snapshot        jsonb not null
                             check (jsonb_typeof(evidence_snapshot) = 'array'
                                    and jsonb_array_length(evidence_snapshot) >= 1),
  claim_hash               text not null,
  gated                    boolean not null default false,   -- company-level: investor-gated
  created_at               timestamptz not null default now(),
  -- the subject reference must match the subject_kind
  check (
    (subject_kind = 'procurement'          and subject_procurement_id is not null) or
    (subject_kind = 'organization_category' and subject_organization_id is not null)
  )
);

create index if not exists idx_predictions_subject_proc
  on predictions (subject_procurement_id) where subject_procurement_id is not null;
create index if not exists idx_predictions_open
  on predictions (horizon_ends_on);

-- Immutability, defense in depth: a trigger refuses any UPDATE or DELETE, so
-- even a service_role or dashboard edit cannot alter a frozen claim.
create or replace function predictions_are_immutable() returns trigger
  language plpgsql as $$
begin
  raise exception 'predictions are immutable: % on prediction %', tg_op,
    coalesce(old.id, new.id);
end $$;

drop trigger if exists trg_predictions_no_update on predictions;
create trigger trg_predictions_no_update before update or delete on predictions
  for each row execute function predictions_are_immutable();

-- Anti-backdating: made_at is the authoritative "we called it by then" stamp
-- and the whole value proposition rests on it. The client supplies made_at
-- (so it can fold it into claim_hash), but this trigger rejects any value not
-- within a two-minute window of the SERVER clock, so a claim cannot be
-- inserted with a backdated timestamp. (Post-insert edits are already blocked
-- by immutability; this closes the insert-time gap.) Proof against manipulation
-- of the server clock itself comes from the external anchor below.
create or replace function predictions_made_at_is_now() returns trigger
  language plpgsql as $$
begin
  if new.made_at < now() - interval '2 minutes'
     or new.made_at > now() + interval '2 minutes' then
    raise exception 'predictions.made_at (%) must be the current time; backdating is refused',
      new.made_at;
  end if;
  return new;
end $$;

drop trigger if exists trg_predictions_made_at on predictions;
create trigger trg_predictions_made_at before insert on predictions
  for each row execute function predictions_made_at_is_now();

-- ---- prediction_outcomes (append-only reconciliation) -----------------------
-- Kept separate so the claim stays frozen. The reconcile job inserts a
-- 'proposed' outcome; a human confirms it. The hit-rate view reads the latest
-- confirmed outcome per prediction.
create table if not exists prediction_outcomes (
  id                   uuid primary key default gen_random_uuid(),
  prediction_id        uuid not null references predictions(id),
  outcome              text not null
                         check (outcome in ('correct','partial','incorrect','expired','unresolved')),
  settling_document_id uuid references documents(id),   -- the public doc that settled it
  resolved_on          date,
  note                 text,
  status               text not null default 'proposed'
                         check (status in ('proposed','confirmed')),
  proposed_by          text not null default 'reconcile@v1',
  confirmed_at         timestamptz,
  created_at           timestamptz not null default now()
);

create index if not exists idx_outcomes_prediction
  on prediction_outcomes (prediction_id, created_at desc);

-- ---- prediction_anchors (external timestamp proof) --------------------------
-- The internal made_at + claim_hash + immutability prove a claim was not
-- edited AFTER it was frozen, and the made_at trigger prevents backdating at
-- insert. But proving to a skeptical third party (an investor, a regulator)
-- that a claim existed by a given date needs an anchor OUTSIDE our own
-- database, one we cannot backdate. This append-only table records where each
-- claim's hash was externally committed: a public git commit whose hash log
-- GitHub timestamps server-side, and/or an OpenTimestamps (Bitcoin-anchored)
-- proof. Because predictions are immutable, the anchor cannot live on the
-- claim row; it is recorded here after the fact by the anchoring job (built
-- with the reconcile unit). One claim may gain several anchors over time.
create table if not exists prediction_anchors (
  id            uuid primary key default gen_random_uuid(),
  prediction_id uuid not null references predictions(id),
  claim_hash    text not null,            -- copied so the anchor is self-contained
  anchor_type   text not null check (anchor_type in ('git_commit','opentimestamps','other')),
  anchor_ref    text not null,            -- commit SHA, .ots reference, etc.
  anchored_at   timestamptz not null default now(),
  note          text,
  created_at    timestamptz not null default now()
);

create index if not exists idx_anchors_prediction
  on prediction_anchors (prediction_id);

-- ---- hit-rate + lead-time view (reviewer-facing) ----------------------------
-- The proof metric. Over confirmed, settled outcomes: the correct rate, and
-- lead time = days between the claim's made_at and the settling document's
-- event date (positive = the call preceded the public evidence). Latest
-- confirmed outcome per prediction wins.
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
left join documents d on d.id = l.settling_document_id;

-- ---- RLS + grants -----------------------------------------------------------
alter table predictions        enable row level security;
alter table prediction_outcomes enable row level security;
alter table prediction_anchors  enable row level security;

-- predictions: reviewer reads all and INSERTs (authoring a frozen claim on
-- approval). No update/delete grant, and the trigger blocks them anyway.
drop policy if exists "pred_read"   on predictions;
create policy "pred_read"   on predictions for select to authenticated using (true);
drop policy if exists "pred_insert" on predictions;
create policy "pred_insert" on predictions for insert to authenticated with check (true);

-- outcomes: reviewer reads all, inserts (manual outcome), and updates
-- (confirming a proposed one). No delete.
drop policy if exists "outcome_read"   on prediction_outcomes;
create policy "outcome_read"   on prediction_outcomes for select to authenticated using (true);
drop policy if exists "outcome_insert" on prediction_outcomes;
create policy "outcome_insert" on prediction_outcomes for insert to authenticated with check (true);
drop policy if exists "outcome_update" on prediction_outcomes;
create policy "outcome_update" on prediction_outcomes for update to authenticated using (true) with check (true);

-- anchors: reviewer reads all; the anchoring job (service_role) inserts. No
-- update/delete: an anchor, like an outcome record, is append-only.
drop policy if exists "anchor_read" on prediction_anchors;
create policy "anchor_read" on prediction_anchors for select to authenticated using (true);

grant select, insert         on table predictions        to authenticated;
grant select, insert, update on table prediction_outcomes to authenticated;
grant select                 on table prediction_anchors  to authenticated;
grant select                 on prediction_scorecard      to authenticated;
-- deliberately NO update/delete on predictions, no delete anywhere, nothing to
-- anon. service_role (reconcile job) bypasses RLS but is ALSO blocked from
-- mutating a frozen claim by the trigger.

commit;
