-- ============================================================================
-- One-off data fix: the 2026-07-14 double-submit.
--
-- Two identical immutable predictions were frozen seconds apart by an accidental
-- double-click:
--   * a8980b00...  made_at 19:03:33  (first click)   -> CANONICAL, stays scored
--   * 27596426...  made_at 19:03:40  (re-submit)      -> DUPLICATE, superseded
-- Same procurement, predicted_rung 4, horizon 9. Recording the later one as a
-- duplicate-of the earlier makes the scorecard count this as ONE call; both
-- rows remain in the ledger (nothing deleted).
--
-- Requires 2026-07-14_prediction_supersessions.sql first. Idempotent: the
-- unique(prediction_id) constraint + guard make re-application a no-op.
-- ============================================================================
begin;

do $$
declare
  dup   uuid;
  canon uuid;
begin
  -- resolve the exact rows from the id prefixes; refuse if a prefix is not
  -- uniquely a single prediction (never guess which claim to set aside).
  select id into strict dup   from predictions where id::text like '27596426%';
  select id into strict canon from predictions where id::text like 'a8980b00%';

  insert into prediction_supersessions
        (prediction_id, supersedes_prediction_id, reason, note)
  values (dup, canon, 'duplicate',
          'accidental double-submit 2026-07-14 ~19:03 (same procurement, rung 4, '
          || 'horizon 9); the 19:03:33 claim is canonical, this 19:03:40 re-submit '
          || 'is set aside so the scorecard counts one call')
  on conflict (prediction_id) do nothing;
exception
  when no_data_found then
    raise exception 'double-submit fix: an id prefix matched no prediction; not applied';
  when too_many_rows then
    raise exception 'double-submit fix: an id prefix matched multiple predictions; not applied';
end $$;

commit;
