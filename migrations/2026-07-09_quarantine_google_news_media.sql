-- ============================================================================
-- Quarantine Google News media_article documents.
--
-- Every media_article captured by the Google News collector links to a
-- news.google.com/rss redirect URL rather than the actual publisher, which
-- violates the provenance rule (every record must link to its real public
-- source). Data-quality review confirmed this is 1200/1200 rows. Titles are
-- also [Source]-prefixed and truncated, and the set includes years-old
-- articles — so the feed is unsound as collected, not merely noisy.
--
-- This does NOT delete the rows (they're kept for audit); it marks them
-- 'irrelevant' so the extractor — which only pulls status='captured' — skips
-- them. Re-collect properly once the Google News collector is fixed to resolve
-- publisher URLs.
--
-- Reviewed, transactional, idempotent: the status='captured' guard means
-- re-running only affects rows still queued, and never re-touches rows already
-- quarantined or legitimately re-captured later.
-- ============================================================================
begin;

update documents
set status = 'irrelevant'
where doc_type = 'media_article'
  and status = 'captured'
  and url ilike '%news.google.com%';

commit;
