-- ============================================================================
-- documents.reference_number: the solicitation / procurement identifier a
-- structured source provides (federal contracts carry procurement_id; a future
-- CanadaBuys tender enrichment carries the same solicitation number).
--
-- WHY THIS EXISTS: the procurement proposer hard-keys candidate procurements on
-- a reference number so an award and its originating tender cluster into one
-- procurement. Until now the proposer could only parse a reference from a
-- signal's title / document title / document URL, never the document body, so a
-- reference buried in an award's text was invisible to the hard-key path.
-- Promoting it to a first-class, indexed column that the proposer reads
-- directly makes the hard key genuine and cheap (no body load), and lets a
-- tender and an award for the same solicitation truly cluster.
--
-- Additive, transactional, idempotent. No collector, workflow, or extraction
-- path is forced to set it; sources that have a structured reference populate
-- it, everyone else leaves it NULL.
-- ============================================================================
begin;

alter table documents
  add column if not exists reference_number text;

comment on column documents.reference_number is
  'Structured solicitation / procurement identifier when the source provides '
  'one (federal contracts procurement_id, future CanadaBuys solicitation '
  'number). The procurement proposer hard-keys on it so an award and its '
  'tender cluster into one procurement. NULL when the source has no such id.';

-- Lookups by reference are how the proposer finds co-solicitation documents.
create index if not exists idx_documents_reference_number
  on documents (reference_number)
  where reference_number is not null;

commit;
