-- ============================================================================
-- Row-Level Security for the private review app.
--
-- The review app (web/) is served on a public Vercel URL and authenticates
-- with the ANON key + a Supabase Auth session. RLS is what actually protects
-- the data: with these policies, an unauthenticated request (anyone who finds
-- the URL) can read/write NOTHING; only a logged-in session can.
--
-- The collector/extractor use the SERVICE_ROLE key, which BYPASSES RLS, so the
-- pipeline is unaffected by anything here.
--
-- ⚠️ BLAST RADIUS: enabling RLS changes access for the anon key on these tables.
-- The collector (service_role) is fine. If any *other* consumer reads these
-- tables via the anon/publishable key, it will now be denied unless it, too, is
-- authenticated. There are no such consumers today — but confirm before running.
--
-- Reviewed, transactional, idempotent (enable-RLS is a no-op if already on;
-- policies are dropped-if-exists then recreated).
-- ============================================================================
begin;

alter table signals        enable row level security;
alter table documents      enable row level security;
alter table organizations  enable row level security;
alter table categories     enable row level security;

-- signals: authenticated sessions may read and update (approve/reject/notes).
drop policy if exists "review_read_signals"   on signals;
create policy "review_read_signals"   on signals for select to authenticated using (true);
drop policy if exists "review_update_signals" on signals;
create policy "review_update_signals" on signals for update to authenticated using (true) with check (true);

-- Joined lookup tables: read-only for the review UI.
drop policy if exists "review_read_documents"     on documents;
create policy "review_read_documents"     on documents     for select to authenticated using (true);
drop policy if exists "review_read_organizations" on organizations;
create policy "review_read_organizations" on organizations for select to authenticated using (true);
drop policy if exists "review_read_categories"    on categories;
create policy "review_read_categories"    on categories    for select to authenticated using (true);

commit;
