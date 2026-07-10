-- ============================================================================
-- Base table GRANTs for the private review app's `authenticated` role.
--
-- COMPANION TO: 2026-07-09_signals_rls_review.sql. Run that migration first
-- (it enables RLS and creates the policies); run this one to grant the base
-- table privileges those policies sit on top of.
--
-- WHY THIS IS NEEDED (and separate):
-- Postgres enforces two independent checks per query, AND-ed, in this order:
--   1. table privilege (GRANT) — may this role touch the table at all?
--   2. RLS policy            — which rows may it see/change?
-- The GRANT check runs FIRST. Our tables were created by raw SQL migrations,
-- not through the Supabase dashboard/API, so the `authenticated` role never
-- received the table GRANTs that the dashboard would have added automatically.
-- Result: the review app (anon key + Auth session -> `authenticated` role) hits
--   "permission denied for table signals"
-- at the GRANT layer, before the RLS policies are ever evaluated. (A pure RLS
-- denial would instead return 0 rows, not a permission error.)
--
-- The collector/extractor use the SERVICE_ROLE key, which has its own grants
-- and BYPASSES RLS, so nothing here affects the pipeline.
--
-- LEAST PRIVILEGE: exactly mirrors the RLS policies in the companion migration
-- — SELECT on the four tables the UI reads, UPDATE on signals for the review
-- actions. No privileges to `anon` (stays denied at both layers). No
-- INSERT/DELETE, and nothing beyond SELECT on the three lookup tables.
--
-- Reviewed, transactional, idempotent (re-granting an existing privilege is a
-- no-op).
-- ============================================================================
begin;

-- SELECT for the review UI's queue + its organization/category/document joins.
grant select on table signals, documents, organizations, categories to authenticated;

-- UPDATE on signals only: approve/reject/notes. (PostgREST returns the updated
-- row by default, which also needs the SELECT granted above.)
grant update on table signals to authenticated;

commit;
