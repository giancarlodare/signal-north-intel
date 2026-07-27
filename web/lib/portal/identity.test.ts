import { test } from "node:test";
import assert from "node:assert/strict";

import { memberIdentity } from "./identity.ts";

test("full name renders initials and short name", () => {
  assert.deepEqual(memberIdentity("m.chen@x.ca", "Morgan Chen"), {
    initials: "MC",
    shortname: "M. Chen",
  });
});

test("three-part name uses first two initials, last surname", () => {
  assert.deepEqual(memberIdentity(null, "Giancarlo Da Re"), {
    initials: "GD",
    shortname: "G. Re",
  });
});

test("single name stands as itself", () => {
  assert.deepEqual(memberIdentity(null, "Cher"), {
    initials: "C",
    shortname: "Cher",
  });
});

test("no name falls back to the email local part, nothing invented", () => {
  assert.deepEqual(memberIdentity("giancarlo97dare@gmail.com"), {
    initials: "GI",
    shortname: "giancarlo97dare",
  });
});

test("nothing at all degrades safely", () => {
  assert.deepEqual(memberIdentity(null, null), {
    initials: "?",
    shortname: "Member",
  });
});
