-- ============================================================================
-- Infrastructure Ontario MERX buyer page (MERX breadth, operator priority
-- buyer: carries the OPP capital signal). PASTE ON OPERATOR GO ONLY, after
-- the validation read:
--   run 30355182846: all 4 tabs live (open 4 / closed 25 / awarded 25 /
--   bid-results 4), 58 abstracts, reference parse 81%, closing parse 55%.
--   The reference misses are ABSENT AT SOURCE (advance notices and
--   RFQ-to-construct shells print no reference number), not parser
--   failures; identity keys on the MERX id, so references are linkage
--   enrichment, not identity. Closing-date misses are the amended/aged
--   ceiling recorded for Ottawa; published_on stays NULL honestly.
-- Provenance: PENDING the IO official page link confirmation (the guessed
-- procurement-opportunities URL 404s); operator browser check or the found
-- page URL goes here before paste.
-- Enablement effect: the tenders_merx roster collects IO on daily-collect
-- (self-maintaining). Historical drains stay cost-gated: the awarded/closed
-- history is sized by a paging count and comes to the operator as an
-- envelope BEFORE any deepened pull.
-- URL-keyed, idempotent.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Infrastructure Ontario MERX solicitations',
       'https://www.merx.com/infrastructureontario',
       'gov_website'::source_type, 'provincial'::jurisdiction_level,
       'scraper', 'daily'
where not exists (select 1 from sources
  where url = 'https://www.merx.com/infrastructureontario');

commit;
