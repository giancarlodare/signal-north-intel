-- ============================================================================
-- Grants collectors, step 2 of 2: sources rows for the three grants pages.
-- Run ONLY AFTER 2026-07-11_grants_doc_types.sql has committed.
--
-- Pattern notes carried from the newsroom seed (both lessons kept):
--   1. Explicit ::source_type / ::jurisdiction_level casts — bare literals
--      in insert…select arrive as text and 42804 the enum columns.
--   2. Idempotency guards keyed on url (pure ASCII), never on name — the
--      em-dash in names has silently defeated name-keyed guards twice.
--
-- FIXED 2026-07-11 (third enum lesson): sources.collector is an ENUM
-- (collector_method: scraper | rss | api | firecrawl | manual) — the first
-- version invented per-module labels ('grants_ontario') and was rejected
-- with "invalid input value for enum collector_method". Nothing in code
-- routes on this column (workflows invoke the modules directly; source
-- resolution is URL-keyed), so all three rows are honestly 'scraper'.
-- Which module owns a row is recorded here instead: the two Ontario rows
-- belong to src/grants_ontario.py, the PS Canada row to
-- src/grants_pscanada.py.
--
-- Three rows:
--   - Ontario open funding directory — DAILY (new programs and deadline
--     changes are the signal).
--   - Ontario closed-funding archive — ONE-TIME baseline corpus, cadence
--     'once'; the collector's --baseline flag crawls it a single time.
--     Separate row so archive documents attribute to the page they actually
--     came from (provenance rule).
--   - PS Canada funding-programs index — WEEKLY.
-- ============================================================================
begin;

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Ontario — Available Funding Opportunities',
       'https://www.ontario.ca/page/available-funding-opportunities-ontario-government',
       'gov_website'::source_type, 'provincial'::jurisdiction_level,
       'scraper'::collector_method, 'daily'
where not exists (select 1 from sources
  where url = 'https://www.ontario.ca/page/available-funding-opportunities-ontario-government');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Ontario — Closed Funding Opportunities (baseline archive)',
       'https://www.ontario.ca/page/closed-funding-opportunities-ontario-government',
       'gov_website'::source_type, 'provincial'::jurisdiction_level,
       'scraper'::collector_method, 'once'
where not exists (select 1 from sources
  where url = 'https://www.ontario.ca/page/closed-funding-opportunities-ontario-government');

insert into sources (name, url, source_type, jurisdiction, collector, cadence)
select 'Public Safety Canada — Funding Programs',
       'https://www.publicsafety.gc.ca/cnt/rsrcs/fndng-prgrms/index-en.aspx',
       'gov_website'::source_type, 'federal'::jurisdiction_level,
       'scraper'::collector_method, 'weekly'
where not exists (select 1 from sources
  where url = 'https://www.publicsafety.gc.ca/cnt/rsrcs/fndng-prgrms/index-en.aspx');

commit;

-- Verify (expect 3 rows; URL-keyed like the guards — collector no longer
-- distinguishes modules):
--   select name, url, source_type, jurisdiction, collector, cadence
--   from sources
--   where url in (
--     'https://www.ontario.ca/page/available-funding-opportunities-ontario-government',
--     'https://www.ontario.ca/page/closed-funding-opportunities-ontario-government',
--     'https://www.publicsafety.gc.ca/cnt/rsrcs/fndng-prgrms/index-en.aspx');
