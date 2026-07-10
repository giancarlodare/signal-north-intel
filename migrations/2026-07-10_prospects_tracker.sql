-- ============================================================================
-- SIGNAL NORTH — Prospects tracker (Target 100 + discovery pipeline)
--
-- Two tables powering a private sales-pipeline page in the review app:
--   prospects              — the Target 100 list (company, category, tier,
--                            reference-candidate flag, conflict flag, warm
--                            path, wave, status)
--   prospect_interactions  — dated log of touches per prospect
--
-- Design notes:
--   * Transactional, idempotent, additive-only (create if not exists;
--     policies dropped-and-recreated; trigger guarded).
--   * RLS + GRANTs included IN THIS FILE so the review app works on day one
--     (lesson from 2026-07-09: RLS policies without base GRANTs = permission
--     denied). anon gets nothing; authenticated gets select/insert/update.
--     No DELETE for authenticated — status changes, never row deletion.
--     service_role bypasses RLS as usual.
--   * GOVERNANCE (read before entering data): interaction notes must be
--     venture-clean. Record facts about venture conversations only. Nothing
--     learned in an official government capacity goes in this table; warm
--     paths are described neutrally ("known via sector events"), never via
--     the day job. If in doubt, leave the note out.
-- ============================================================================

begin;

-- ---- prospects --------------------------------------------------------------
create table if not exists prospects (
  id                       uuid primary key default gen_random_uuid(),
  company_name             text not null unique,
  category                 text not null check (category in (
                             'body_worn_video','drones_counter_drone','records_cad',
                             'ng911','cybersecurity','communications',
                             'vehicles_upfitting','protective_equipment','forensics',
                             'training_simulation','surveillance_sensing','fire_paramedic',
                             'corrections','border_screening','intelligence_analytics',
                             'marine_tactical','defence_dual_use','security_services',
                             'gov_it_staffing','other')),
  tier                     text not null default 'professional_tier' check (tier in (
                             'founding_candidate',   -- the $5K founding cohort shortlist
                             'professional_tier',    -- $12K prospects, approach post-founding
                             'team_enterprise_tier', -- large firms; 2027+ conversations
                             'watch_only',           -- track, do not approach yet
                             'do_not_approach')),    -- conflict / political / protocol
  is_reference_candidate   boolean not null default false,  -- the one ⭐ per category
  conflict_flag            boolean not null default false,
  conflict_note            text,
  warm_path                text,             -- neutral description only (see header)
  wave                     smallint not null default 3 check (wave in (1,2,3)),
  status                   text not null default 'not_contacted' check (status in (
                             'not_contacted','warm','contacted','meeting_booked',
                             'committed','subscribed','declined','do_not_approach')),
  hq_location              text,
  notes                    text,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);

drop trigger if exists trg_prospects_updated on prospects;
create trigger trg_prospects_updated before update on prospects
  for each row execute function set_updated_at();

-- ---- prospect_interactions --------------------------------------------------
create table if not exists prospect_interactions (
  id               uuid primary key default gen_random_uuid(),
  prospect_id      uuid not null references prospects(id) on delete cascade,
  occurred_on      date not null default current_date,
  interaction_type text not null default 'note' check (interaction_type in (
                     'note','email','call','meeting','event','referral','other')),
  summary          text not null,
  follow_up        text,
  follow_up_due    date,
  created_at       timestamptz not null default now()
);

create index if not exists idx_interactions_prospect
  on prospect_interactions (prospect_id, occurred_on desc);

-- ---- Row-Level Security + base grants (both layers, together) ---------------
alter table prospects              enable row level security;
alter table prospect_interactions  enable row level security;

drop policy if exists "pipeline_read_prospects"    on prospects;
create policy "pipeline_read_prospects"    on prospects
  for select to authenticated using (true);
drop policy if exists "pipeline_insert_prospects"  on prospects;
create policy "pipeline_insert_prospects"  on prospects
  for insert to authenticated with check (true);
drop policy if exists "pipeline_update_prospects"  on prospects;
create policy "pipeline_update_prospects"  on prospects
  for update to authenticated using (true) with check (true);

drop policy if exists "pipeline_read_interactions"   on prospect_interactions;
create policy "pipeline_read_interactions"   on prospect_interactions
  for select to authenticated using (true);
drop policy if exists "pipeline_insert_interactions" on prospect_interactions;
create policy "pipeline_insert_interactions" on prospect_interactions
  for insert to authenticated with check (true);
drop policy if exists "pipeline_update_interactions" on prospect_interactions;
create policy "pipeline_update_interactions" on prospect_interactions
  for update to authenticated using (true) with check (true);

grant select, insert, update on table prospects             to authenticated;
grant select, insert, update on table prospect_interactions to authenticated;
-- deliberately NO delete grant, and nothing to anon.

commit;
