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

// The public marketing site (Wave 3 stage 5, Claude Design incorporation).
// These paths are reachable WITHOUT auth only when the portal flag is on;
// while dark they behave exactly as before (unauthenticated -> /login), so
// deploying the marketing pages changes nothing until the operator flips
// PORTAL_ENABLED. Exact matches: the site has no nested public routes.
//
// /join is PUBLIC and must stay so: it is the page where someone who has no
// account asks for one. Gating it behind a session would mean you need an
// account to get an account, which is the exact state the operator's
// 2026-08-02 ruling removes.
export const SITE_PATHS = [
  "/",
  "/about",
  "/pricing",
  "/contact",
  "/join",
  // Where Stripe returns after a checkout-first purchase (change A). The buyer
  // has no session yet -- the webhook is still provisioning -- so this must be
  // publicly reachable, or a paid customer would be bounced to /login the
  // instant their payment succeeds.
  "/join/thank-you",
] as const;

export function isSitePath(path: string): boolean {
  return (SITE_PATHS as readonly string[]).includes(path);
}

// MACHINE ENDPOINTS. These are called by third parties that will never carry
// a Supabase session cookie, and they authenticate themselves by a mechanism
// STRONGER than one: the Stripe webhook verifies an HMAC signature over the
// raw body and refuses outright without STRIPE_WEBHOOK_SECRET.
//
// Without this exemption the gate would redirect an unauthenticated POST to
// /login (307), in EVERY flag state, because an API route is neither a site
// path nor a member path. Stripe would read the redirect as a failed delivery
// and retry forever, so a paying member would never be granted access and the
// only symptom would be silence.
//
// Keep this list minimal and keep the rule literal: a path belongs here only
// if it carries its own cryptographic authentication.
const MACHINE_PATHS = ["/api/stripe/webhook"] as const;

export function isMachinePath(path: string): boolean {
  return (MACHINE_PATHS as readonly string[]).includes(path);
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
  // Checked BEFORE the authentication branch and in every flag state: these
  // endpoints authenticate themselves and must be reachable while dark.
  if (isMachinePath(path)) return "allow";
  if (!authenticated) {
    if (path === "/login") return "allow";
    // Magic-link landing: must be reachable unauthenticated in every flag
    // state, or the emailed link could never establish a session.
    if (path === "/auth/confirm") return "allow";
    // Marketing site: public once the flag is on; dark (to-login) before.
    if (enabled && isSitePath(path)) return "allow";
    return "to-login";
  }

  // Flag OFF. Pre-Wave-3 behavior for the marketing/operator surfaces (no role
  // gating), with ONE change from change A (operator 2026-08-03): an
  // AUTHENTICATED session may reach the member surface regardless of the flag.
  //
  // WHY THIS CHANGED. The staged-dark contract hid the member surface behind a
  // 404 even from a signed-in member, which coupled "a member can use what they
  // paid for" to the marketing-site flag flip. Checkout-first deliberately
  // decouples them: a purchase provisions an account and emails a sign-in link
  // while the flag is still off, and that member must land in their portal, not
  // a 404. Hiding from the PUBLIC is unaffected -- an unauthenticated request
  // was already handled above (to-login), never reaching here. The paywall
  // (RequirePaid) still governs every product page, so "reachable" is not
  // "readable": an unpaid session is redirected to /portal/account.
  if (!enabled) {
    return "allow";
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
