-- 2026-08-02: signals.relevance -- the materiality/relevance split
-- (docs/lens-redesign-design.md, approved 2026-08-02 with the evening
-- amendment: inclusion gates on relevance, threshold decided from the
-- calibration batch).
--
-- Relevance is how squarely a signal sits in the public-safety
-- procurement lane, SEPARATE from materiality (how big it is). Scored
-- 1..5 by the capped calibration and backfill jobs. NULL means not yet
-- scored, and the lens treats NULL as unscored -- never as zero.
--
-- ARCHITECTURE NOTE (docs/data-architecture-principles.md): this column
-- stores relevance(item, generic-context) -- the evaluation of the
-- relevance function at the generic point, never the function itself.
-- The scorer keeps context as a parameter.
alter table signals add column if not exists relevance smallint
  check (relevance between 1 and 5);
comment on column signals.relevance is
  'Generic-context relevance 1..5 (lens redesign 2026-08-02); NULL = unscored.';
