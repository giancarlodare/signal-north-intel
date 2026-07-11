-- ============================================================================
-- documents.date_precision — how precise published_on actually is.
--
-- Peel's document filenames encode {agenda-item}-{MM}-{YY} (verified against
-- every document where a full date was independently derivable), which dates
-- a document to its meeting MONTH but not a day. Rather than fabricate day=01
-- silently or discard the month, the precision is explicit in the data:
--   'day'   — published_on is a real calendar date (default; all prior rows)
--   'month' — published_on's year+month are real, its day is the conventional
--             01 placeholder. Renderers MUST show "Apr 2026", never a full
--             date. (Review page + future brief generator; docs/ROADMAP.md.)
--
-- Additive, idempotent, transactional.
-- ============================================================================
begin;

alter table documents add column if not exists date_precision text
  not null default 'day' check (date_precision in ('day', 'month'));

commit;
