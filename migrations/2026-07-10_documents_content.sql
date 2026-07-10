-- ============================================================================
-- documents.content — full-text body storage for rich document types.
--
-- Until now every collected doc_type was title-only (CSV rows, RSS headlines),
-- so the extractor fed Claude the title as the body. The board-minutes
-- collector is the first source with real bodies (PDF/HTML minutes and
-- agendas), and it stores the extracted text here so the extraction pipeline
-- has substance to read. Nullable and additive: existing rows and title-only
-- collectors are unaffected; the extractor falls back to the title when
-- content is null.
--
-- Reviewed, transactional, idempotent.
-- ============================================================================
begin;

alter table documents add column if not exists content text;

commit;
