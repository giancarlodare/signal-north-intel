# Member gate smoke test (run AFTER the DDL paste, decision D4)

The gate policy is unit-tested (roles.test.ts). The DATABASE half (RLS) can
only be verified against a live DB with the policies applied, so it is a
manual/CI check the operator runs once at enablement, not part of `npm test`:

1. Provision a throwaway member account (app_metadata.sn_role = "member").
2. Signed in as that member, assert:
   - a published brief READ returns rows;
   - `procurements`, `predictions`, `sources` reads return ZERO rows;
   - `demand_arc_profiles` returns only significance='published' rows (today: none);
   - every INSERT/UPDATE/DELETE is rejected.
3. Signed in as the operator (after sign-out/in), assert full access is intact.

Green here is the proof the gate holds at the database, not just the UI.
Wire this as a CI job against a disposable member JWT once PORTAL_ENABLED flips.
