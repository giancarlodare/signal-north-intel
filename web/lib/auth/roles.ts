// Wave 3 stage 1: role + flag plumbing (functional layer, no styling).
//
// This is the CODE half of the client-facing gate. The DATABASE half (RLS
// policies in migrations/2026-07-27_wave3_member_rls.sql) is the real
// enforcement; this layer is the app-side convenience that routes a session
// to the right surface and keeps the whole thing dark until the operator
// flips the flag.
//
// STAGED-DARK CONTRACT: every role behavior here is keyed on PORTAL_ENABLED.
// While the flag is off (the default), the app behaves EXACTLY as it did
// before Wave 3 (auth-only, single surface), so deploying this PR changes
// nothing in production until the operator both pastes the DDL and flips the
// flag. That ordering is deliberate: the operator role claim must exist
// (DDL, decision D4) before role gating turns on, or the operator app would
// lock its own owner out.

import type { SupabaseClient, User } from "@supabase/supabase-js";

export type SnRole = "operator" | "member";

// D5: PORTAL_ENABLED is a server-side env var, default OFF. Never exposed to
// the client bundle (no NEXT_PUBLIC_ prefix), so the flag state is not
// guessable from the browser.
export function portalEnabled(): boolean {
  return process.env.PORTAL_ENABLED === "true";
}

// D1 (recommended: JWT app_metadata; fail-closed to member). This function is
// the ONLY place that reads where the role lives, so if D1 resolves to a
// roles-table instead, only this body changes and every caller is unaffected.
// A session with no role claim is a MEMBER: least privilege by default, so a
// mis-provisioned account can never accidentally read the operator surface.
export function roleFromUser(user: User | null): SnRole {
  const claim = (user?.app_metadata as Record<string, unknown> | undefined)?.[
    "sn_role"
  ];
  return claim === "operator" ? "operator" : "member";
}

export async function currentRole(
  supabase: SupabaseClient
): Promise<SnRole> {
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return roleFromUser(user);
}

// The route surfaces, as data so the middleware and any server component agree
// on one source of truth. Operator pages are the existing internal app;
// member pages are the Wave 3 portal (its own route group, stage 2+).
export const OPERATOR_PREFIXES = [
  "/corpus",
  "/procurements",
  "/predictions",
  "/discovery",
  "/prospects",
  "/brief",
] as const;

export const MEMBER_PREFIX = "/portal" as const;

export function isOperatorPath(path: string): boolean {
  return OPERATOR_PREFIXES.some(
    (p) => path === p || path.startsWith(p + "/")
  );
}

export function isMemberPath(path: string): boolean {
  return path === MEMBER_PREFIX || path.startsWith(MEMBER_PREFIX + "/");
}

// The gate decision for a request, given the flag, the role, and the path.
// Pure and unit-testable (no I/O), so the policy is verified by test, not by
// reading middleware control flow.
//   "allow"        proceed
//   "not-found"    render 404 (member surface while dark; hides its existence)
//   "to-portal"    a member hitting an operator page is sent to their surface
//   "to-login"     unauthenticated (handled upstream, included for completeness)
export type GateOutcome = "allow" | "not-found" | "to-portal" | "to-login";

export function gate(args: {
  enabled: boolean;
  authenticated: boolean;
  role: SnRole;
  path: string;
}): GateOutcome {
  const { enabled, authenticated, role, path } = args;
  if (!authenticated) return path === "/login" ? "allow" : "to-login";

  // Flag OFF: pre-Wave-3 behavior. Member routes do not exist yet (404),
  // everything else is allowed exactly as before. No role gating.
  if (!enabled) {
    return isMemberPath(path) ? "not-found" : "allow";
  }

  // Flag ON: role gating is live.
  if (isMemberPath(path)) {
    // Operators may view the member surface; members belong here.
    return "allow";
  }
  if (isOperatorPath(path)) {
    return role === "operator" ? "allow" : "to-portal";
  }
  // Neutral paths (/, /login handled above) are allowed to either role.
  return "allow";
}
