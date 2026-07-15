-- ============================================================================
-- Published brief delivery: email send tracking + the one honest standing
-- exhibit (docs/published-brief-design.md).
--
--   * briefs.sent_at: set once when a published brief is emailed, so "Send to
--     me" is idempotent and the delivery is part of the record.
--   * award_volume_by_quarter: the ONLY exhibit honest at current data density,
--     the count of award notices by quarter and jurisdiction. We hold 2,758 Peel
--     municipal awards back to 2017, so the municipal slice is dense and real.
--     Value, cross-jurisdiction comparison, the demand ladder, and recompete
--     windows are deliberately NOT built (none beats a wrong chart); they turn on
--     as value, coverage, and term extraction land.
--
-- Additive, transactional, idempotent.
-- ============================================================================
begin;

alter table briefs add column if not exists sent_at timestamptz;

-- Count of award_notice documents by quarter of the event date, per source
-- jurisdiction. An aggregate of public award notices, so it carries no
-- row-level sensitivity; the reader-facing exhibit filters to 'municipal'
-- (currently Region of Peel) and labels its basis honestly.
create or replace view award_volume_by_quarter as
select s.jurisdiction::text                                          as jurisdiction,
       date_trunc('quarter', d.published_on)::date                   as quarter_start,
       to_char(date_trunc('quarter', d.published_on), 'YYYY "Q"Q')   as quarter_label,
       count(*)::int                                                 as awards
  from documents d
  join sources s on s.id = d.source_id
 where d.doc_type = 'award_notice'
   and d.published_on is not null
 group by s.jurisdiction, date_trunc('quarter', d.published_on);

grant select on award_volume_by_quarter to authenticated;

commit;
