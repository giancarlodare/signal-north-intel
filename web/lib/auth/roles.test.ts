// Unit tests for the gate policy (Wave 3 stage 1). The RLS is the real
// enforcement; this proves the app-side routing policy, including the
// staged-dark contract (flag off => pre-Wave-3 behavior).
import { test } from "node:test";
import assert from "node:assert/strict";

import { gate, roleFromUser, isOperatorPath, isMemberPath } from "./roles.ts";
import type { User } from "@supabase/supabase-js";

function user(role?: string): User {
  return { app_metadata: role ? { sn_role: role } : {} } as unknown as User;
}

test("roleFromUser fails closed to member", () => {
  assert.equal(roleFromUser(null), "member");
  assert.equal(roleFromUser(user()), "member");
  assert.equal(roleFromUser(user("nonsense")), "member");
  assert.equal(roleFromUser(user("operator")), "operator");
  assert.equal(roleFromUser(user("member")), "member");
});

test("path classifiers", () => {
  assert.ok(isOperatorPath("/corpus"));
  assert.ok(isOperatorPath("/procurements/123"));
  assert.ok(!isOperatorPath("/portal"));
  assert.ok(isMemberPath("/portal"));
  assert.ok(isMemberPath("/portal/watchlist"));
  assert.ok(!isMemberPath("/corpus"));
});

test("flag OFF is exact pre-Wave-3 behavior: no role gating, member 404", () => {
  // an operator page is allowed with NO role gating (member role, flag off)
  assert.equal(
    gate({ enabled: false, authenticated: true, role: "member", path: "/corpus" }),
    "allow"
  );
  // the member surface does not exist while dark
  assert.equal(
    gate({ enabled: false, authenticated: true, role: "member", path: "/portal" }),
    "not-found"
  );
});

test("flag ON gates operator pages by role", () => {
  assert.equal(
    gate({ enabled: true, authenticated: true, role: "operator", path: "/corpus" }),
    "allow"
  );
  assert.equal(
    gate({ enabled: true, authenticated: true, role: "member", path: "/corpus" }),
    "to-portal"
  );
});

test("flag ON: member surface open to both roles", () => {
  assert.equal(
    gate({ enabled: true, authenticated: true, role: "member", path: "/portal" }),
    "allow"
  );
  assert.equal(
    gate({ enabled: true, authenticated: true, role: "operator", path: "/portal" }),
    "allow"
  );
});

test("unauthenticated always routes to login except on login", () => {
  assert.equal(
    gate({ enabled: true, authenticated: false, role: "member", path: "/corpus" }),
    "to-login"
  );
  assert.equal(
    gate({ enabled: false, authenticated: false, role: "member", path: "/login" }),
    "allow"
  );
});

test("marketing site: public only when the flag is on", () => {
  // Flag ON: the four site paths open without auth.
  for (const p of ["/", "/about", "/pricing", "/contact"]) {
    assert.equal(
      gate({ enabled: true, authenticated: false, role: "member", path: p }),
      "allow",
      p
    );
  }
  // Flag OFF: exactly the pre-incorporation behavior (dark, to-login).
  for (const p of ["/", "/about", "/pricing", "/contact"]) {
    assert.equal(
      gate({ enabled: false, authenticated: false, role: "member", path: p }),
      "to-login",
      p
    );
  }
  // Non-site unauthenticated paths stay closed even with the flag on.
  assert.equal(
    gate({ enabled: true, authenticated: false, role: "member", path: "/portal" }),
    "to-login"
  );
  // Site paths are exact matches: a nested unknown path is not public.
  assert.equal(
    gate({ enabled: true, authenticated: false, role: "member", path: "/about/team" }),
    "to-login"
  );
});
