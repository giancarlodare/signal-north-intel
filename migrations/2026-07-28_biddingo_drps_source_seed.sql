-- ============================================================================
-- Biddingo buyer page: Durham Regional Police Service (/m/drps).
-- PASTE ON OPERATOR GO ONLY, after the validation report clears.
-- Provenance: drps.ca/about-us/procurement-services/ names Biddingo as the
--   service's posting channel (operator browse 2026-07-20; the branded
--   bids&tenders tenant stays permanently parked as legacy/secondary).
-- Robots: biddingo.com is wildcard-allow; verified under the renamed
--   SignalNorthIntel/1.0 UA in probe run 30356741517 (the old name's
--   "Collector" token falsely matched a banned-tool group aimed at a
--   different product).
-- Structure: probe run 30356971071 -- the page's own public REST call
--   (restapi/bidding/list/noauthorize) returns the full 38-bid portfolio,
--   refs back to 2023, dedicated tenderNumber/bidStatus/closing fields.
-- Enablement effect: src/tenders_biddingo collects DRPS on daily-tenders
--   (one rendered page per run, self-maintaining). The full portfolio is 38
--   rows in one response, so there is no history drain to cost-gate; the
--   ~38-doc extraction backlog rides the capped daily forward pass.
-- URL-keyed, idempotent.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Durham Regional Police Service — Biddingo bids',
       'https://www.biddingo.com/m/drps',
       'gov_website'::source_type, 'municipal'::jurisdiction_level,
       'scraper', 'daily'
where not exists (select 1 from sources
  where url = 'https://www.biddingo.com/m/drps');

commit;
