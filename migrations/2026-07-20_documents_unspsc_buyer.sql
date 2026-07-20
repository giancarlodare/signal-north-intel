-- ============================================================================
-- CanadaBuys tender enrichment (docs/canadabuys-enrichment-design.md,
-- approved 2026-07-20): two structured columns the open-data CSV already
-- carries and the collector previously discarded.
--
-- documents.unspsc_codes: buyer-published UNSPSC classification codes,
-- an ARRAY because one tender routinely lists several. text[] not int[]:
-- codes are fixed-width 8-digit identifiers with meaningful leading zeros.
-- The three payoffs (watchlist backbone, factual "who bids" basis, backtest
-- category spine) all filter on this column; the GIN index serves prefix and
-- containment queries. Segment rollup (first 2 digits) is DERIVED at query
-- time, never stored. Nothing may assume codes exist: municipal portals
-- publish none and every non-CanadaBuys source leaves this NULL.
--
-- documents.buyer_name: the contracting entity exactly as published, for
-- deterministic org resolution and reporting. Resolution to the canonical
-- organizations list stays downstream; NULL wherever the source has no
-- structured buyer field.
--
-- Additive, transactional, idempotent.
-- ============================================================================
begin;

alter table documents
  add column if not exists unspsc_codes text[];

comment on column documents.unspsc_codes is
  'Buyer-published UNSPSC codes (8-digit strings, several per tender). '
  'Source: CanadaBuys open-data CSVs. NULL for sources that publish none '
  '(municipal portals, RSS); nothing may assume presence.';

create index if not exists idx_documents_unspsc_codes
  on documents using gin (unspsc_codes)
  where unspsc_codes is not null;

alter table documents
  add column if not exists buyer_name text;

comment on column documents.buyer_name is
  'Contracting entity name exactly as the source publishes it. Canonical '
  'org resolution happens downstream; NULL when the source has no '
  'structured buyer field.';

commit;
