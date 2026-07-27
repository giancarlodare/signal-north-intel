-- ============================================================================
-- Marketing-site public data functions (operator 2026-07-27).
--
-- The marketing pages are PUBLIC (anon session) and the RLS clamps rightly
-- give anon nothing. Rather than shipping the service key to the web app,
-- these SECURITY DEFINER functions expose EXACTLY the hand-picked aggregates
-- and lists the marketing site needs, nothing else: no raw table access, no
-- parameters that reach into filters, each function returns a fixed shape.
-- The site's rule (operator): every element that would go stale renders from
-- these or is omitted; there is no static fallback.
--
-- APPLY AT OPERATOR GO, pasted AFTER 2026-07-27_signals_public_safety.sql:
-- marketing_closing_soon() filters on signals.public_safety (the vertical
-- teaser shows only the public-safety slice), so that column must exist.
--
-- Definitions of record (what each figure MEANS, so the site stays honest):
--   * "on the record" org  = an organization with at least one live signal.
--   * live contract        = contract_awards with a known end date not yet
--                            passed (coalesce(final_end_on, end_on) >= today).
--   * value on the record  = sum of disclosed value_cad over live contracts.
--   * years of history     = whole years since the earliest awarded_on.
--   * documents each week  = documents captured in the last 7 days.
--   * closing soon         = un-suppressed public-safety tender/grant signals
--                            whose event date (deadline) is in the future,
--                            within 90 days, one row per source document.
--
-- Idempotent (create or replace). Rollback: drop the four functions.
-- ============================================================================

begin;

create or replace function public.marketing_stats()
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  select jsonb_build_object(
    'police_and_boards', (
      select count(*) from organizations o
       where o.org_type in ('police_service', 'police_board')
         and exists (select 1 from signals s
                      where s.organization_id = o.id and s.suppressed = false)),
    'councils_ministries_departments', (
      select count(*) from organizations o
       where o.org_type in ('municipality', 'provincial_ministry',
                            'federal_department')
         and exists (select 1 from signals s
                      where s.organization_id = o.id and s.suppressed = false)),
    'live_contracts_with_end_dates', (
      select count(*) from contract_awards ca
       where coalesce(ca.final_end_on, ca.end_on) >= current_date),
    'live_contract_value_cad', (
      select coalesce(sum(ca.value_cad), 0) from contract_awards ca
       where coalesce(ca.final_end_on, ca.end_on) >= current_date
         and ca.value_cad is not null),
    'earliest_award_year', (
      select extract(year from min(ca.awarded_on))::int from contract_awards ca
       where ca.awarded_on is not null),
    'years_of_award_history', (
      select coalesce(extract(year from age(current_date, min(ca.awarded_on)))::int, 0)
        from contract_awards ca where ca.awarded_on is not null),
    'documents_last_7_days', (
      select count(*) from documents d
       where d.created_at >= now() - interval '7 days')
  );
$$;

create or replace function public.marketing_coverage()
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  with on_record as (
    select o.canonical_name, o.org_type
      from organizations o
     where exists (select 1 from signals s
                    where s.organization_id = o.id and s.suppressed = false)
  )
  select jsonb_build_object(
    'services', (
      select coalesce(jsonb_agg(canonical_name order by canonical_name), '[]'::jsonb)
        from on_record where org_type = 'police_service'),
    'oversight', (
      select coalesce(jsonb_agg(canonical_name order by canonical_name), '[]'::jsonb)
        from on_record where org_type in ('police_board', 'municipality')),
    'government', (
      select coalesce(jsonb_agg(canonical_name order by canonical_name), '[]'::jsonb)
        from on_record where org_type in ('provincial_ministry', 'federal_department'))
  );
$$;

-- plpgsql so the signals.public_safety reference resolves at run time (this
-- file is pasted after the member-read migration; see header).
create or replace function public.marketing_closing_soon()
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare result jsonb;
begin
  with open_items as (
    select distinct on (d.id)
           s.title,
           o.canonical_name as buyer,
           case when d.doc_type = 'tender_notice' then 'Tender' else 'Grant' end as kind,
           d.published_on as close_on,
           (d.published_on - current_date) as days_left
      from signals s
      join documents d on d.id = s.document_id
      left join organizations o on o.id = s.organization_id
     where s.suppressed = false
       and s.public_safety = true
       and d.doc_type in ('tender_notice', 'grant_program', 'grant_award')
       and d.published_on > current_date
       and d.published_on <= current_date + 90
     order by d.id, s.evidence_grade desc nulls last
  )
  select jsonb_build_object(
    'total_open', (select count(*) from open_items),
    'rows', (
      select coalesce(jsonb_agg(x), '[]'::jsonb) from (
        select * from open_items order by close_on asc limit 5
      ) x)
  ) into result;
  return result;
end;
$$;

create or replace function public.marketing_recent_awards()
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(jsonb_agg(x), '[]'::jsonb) from (
    select coalesce(nullif(trim(ca.description), ''), 'Contract award') as title,
           ca.vendor_name as vendor,
           extract(year from coalesce(ca.final_end_on, ca.end_on))::int as end_year
      from contract_awards ca
     where coalesce(ca.final_end_on, ca.end_on) is not null
     order by ca.awarded_on desc nulls last
     limit 3
  ) x;
$$;

grant execute on function public.marketing_stats() to anon, authenticated;
grant execute on function public.marketing_coverage() to anon, authenticated;
grant execute on function public.marketing_closing_soon() to anon, authenticated;
grant execute on function public.marketing_recent_awards() to anon, authenticated;

commit;
