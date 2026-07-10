-- ============================================================================
-- Discovery engine tables (per docs/discovery-engine-design.md, approved).
--
-- Three tables:
--   discovery_blocklist    — rejected-forever domains (aggregators, Google
--                            News, known-bad). A TABLE, not a code constant,
--                            so it is visible/editable from the review app and
--                            rejection history lives with the data. Seeded
--                            with news.google.com + known aggregators below.
--   discovered_sources     — proposed new sources. Weekly job writes here and
--                            ONLY here (plus discovered_entities); approving
--                            in the web app is what creates the sources row.
--   discovered_entities    — proposed orgs / appointments / company-intent /
--                            alias updates, with mandatory evidence.
--
-- Standards: transactional, idempotent, additive-only. RLS + base GRANTs in
-- the same file (the 2026-07-10 lesson). No views (the page queries tables
-- directly). No DELETE grant anywhere; rejection is a status, not a deletion.
--
-- Write model:
--   service_role (weekly job)  — bypasses RLS; proposes and re-proposes.
--   authenticated (review app) — reads everything; updates status/notes;
--                                inserts into blocklist (managing it from the
--                                app later); NEVER inserts proposals.
--   Approval side-effects also need: insert on sources, insert+update on
--   organizations — granted here with matching RLS policies. (organizations
--   RLS is already enabled with a read policy; sources RLS is enabled here.)
--   prospects insert (the "add to prospects" second action) was already
--   granted by 2026-07-10_prospects_tracker.sql.
-- ============================================================================
begin;

-- ---- blocklist ---------------------------------------------------------------
create table if not exists discovery_blocklist (
  id         uuid primary key default gen_random_uuid(),
  domain     text not null unique,        -- matches host == domain or *.domain
  note       text,
  created_at timestamptz not null default now()
);

insert into discovery_blocklist (domain, note)
select v.domain, v.note
from (values
    ('news.google.com',    'Aggregator; provenance-broken redirect URLs (the 1,200-row lesson)'),
    ('google.com',         'Search/aggregation, never a publisher of record'),
    ('feedproxy.google.com','Feed proxy'),
    ('news.yahoo.com',     'Aggregator'),
    ('ca.news.yahoo.com',  'Aggregator'),
    ('msn.com',            'Aggregator'),
    ('flipboard.com',      'Aggregator'),
    ('apple.news',         'Aggregator'),
    ('newsbreak.com',      'Aggregator'),
    ('facebook.com',       'Social media — out of bounds by standing rule'),
    ('twitter.com',        'Social media — out of bounds by standing rule'),
    ('x.com',              'Social media — out of bounds by standing rule'),
    ('linkedin.com',       'Social media — out of bounds by standing rule'),
    ('instagram.com',      'Social media — out of bounds by standing rule'),
    ('reddit.com',         'Social media — out of bounds by standing rule'),
    ('youtube.com',        'Social media — out of bounds by standing rule'),
    ('t.co',               'URL shortener'),
    ('bit.ly',             'URL shortener'),
    ('ow.ly',              'URL shortener')
) as v(domain, note)
where not exists (select 1 from discovery_blocklist b where b.domain = v.domain);

-- ---- discovered_sources -------------------------------------------------------
create table if not exists discovered_sources (
  id                    uuid primary key default gen_random_uuid(),
  domain                text not null unique,           -- idempotency key
  suggested_name        text not null,
  kind                  text not null default 'publisher_other'
                        check (kind in ('newsroom','board','association','publisher_other')),
  sample_urls           text[] not null,
  evidence_document_ids uuid[] not null
                        check (array_length(evidence_document_ids, 1) >= 1),
  mention_count         integer not null default 1,     -- distinct referencing docs
  source_count          integer not null default 1,     -- distinct sources those docs came from
  first_seen_on         date not null default current_date,
  last_seen_on          date not null default current_date,
  proposed_by           text not null,                  -- e.g. 'heuristic@v1'
  status                text not null default 'proposed'
                        check (status in ('proposed','approved','rejected')),
  review_note           text,
  reviewed_at           timestamptz,
  created_source_id     uuid references sources(id),
  created_at            timestamptz not null default now()
);

-- ---- discovered_entities -------------------------------------------------------
create table if not exists discovered_entities (
  id                        uuid primary key default gen_random_uuid(),
  entity_kind               text not null check (entity_kind in
                            ('organization','person_appointment',
                             'company_canada_intent','alias_update')),
  name                      text not null,
  normalized_name           text not null,
  detail                    jsonb not null default '{}',
  existing_organization_id  uuid references organizations(id),
  evidence_document_ids     uuid[] not null
                            check (array_length(evidence_document_ids, 1) >= 1),
  mention_count             integer not null default 1,
  proposed_by               text not null,   -- 'unresolved-orgs@v1' | 'discovery@v1'
  status                    text not null default 'proposed'
                            check (status in ('proposed','approved','rejected')),
  review_note               text,
  reviewed_at               timestamptz,
  created_at                timestamptz not null default now(),
  unique (entity_kind, normalized_name)      -- idempotency key
);

-- ---- RLS + grants (both layers together) ----------------------------------------
alter table discovery_blocklist  enable row level security;
alter table discovered_sources   enable row level security;
alter table discovered_entities  enable row level security;
alter table sources              enable row level security;

drop policy if exists "discovery_read_blocklist"   on discovery_blocklist;
create policy "discovery_read_blocklist"   on discovery_blocklist
  for select to authenticated using (true);
drop policy if exists "discovery_insert_blocklist" on discovery_blocklist;
create policy "discovery_insert_blocklist" on discovery_blocklist
  for insert to authenticated with check (true);
drop policy if exists "discovery_update_blocklist" on discovery_blocklist;
create policy "discovery_update_blocklist" on discovery_blocklist
  for update to authenticated using (true) with check (true);

drop policy if exists "discovery_read_sources_prop"   on discovered_sources;
create policy "discovery_read_sources_prop"   on discovered_sources
  for select to authenticated using (true);
drop policy if exists "discovery_update_sources_prop" on discovered_sources;
create policy "discovery_update_sources_prop" on discovered_sources
  for update to authenticated using (true) with check (true);
-- deliberately NO insert policy: only the weekly job (service_role) proposes.

drop policy if exists "discovery_read_entities_prop"   on discovered_entities;
create policy "discovery_read_entities_prop"   on discovered_entities
  for select to authenticated using (true);
drop policy if exists "discovery_update_entities_prop" on discovered_entities;
create policy "discovery_update_entities_prop" on discovered_entities
  for update to authenticated using (true) with check (true);

-- Approval side-effects:
drop policy if exists "discovery_read_sources"   on sources;
create policy "discovery_read_sources"   on sources
  for select to authenticated using (true);
drop policy if exists "discovery_insert_sources" on sources;
create policy "discovery_insert_sources" on sources
  for insert to authenticated with check (true);

drop policy if exists "discovery_insert_organizations" on organizations;
create policy "discovery_insert_organizations" on organizations
  for insert to authenticated with check (true);
drop policy if exists "discovery_update_organizations" on organizations;
create policy "discovery_update_organizations" on organizations
  for update to authenticated using (true) with check (true);

grant select, insert, update on table discovery_blocklist  to authenticated;
grant select, update         on table discovered_sources   to authenticated;
grant select, update         on table discovered_entities  to authenticated;
grant select, insert         on table sources              to authenticated;
grant insert, update         on table organizations        to authenticated;
-- deliberately NO delete grants anywhere, and nothing to anon.

commit;
