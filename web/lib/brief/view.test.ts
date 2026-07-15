import { test } from "node:test";
import assert from "node:assert/strict";
import { weekLabel, pickLeadAndSupporting } from "./view.ts";
import type { RenderItem } from "./render.ts";

function ri(timing_path: "recent" | "imminent", headline: string): RenderItem {
  return {
    headline, timing_path, vendorSoWhat: null, buyer: null, amountCad: null,
    doc: { doc_type: null, url: null, published_on: null, date_precision: null },
  };
}

test("weekLabel formats a Monday-to-Sunday week", () => {
  assert.equal(weekLabel("2026-07-13"), "13 to 19 July 2026");
});

test("weekLabel spans months and years", () => {
  assert.equal(weekLabel("2026-06-29"), "29 June to 5 July 2026");
  assert.equal(weekLabel("2026-12-28"), "28 December 2026 to 3 January 2027");
});

test("pickLeadAndSupporting leads with the first imminent item", () => {
  const items = [ri("recent", "A"), ri("imminent", "B"), ri("imminent", "C")];
  const { lead, supporting } = pickLeadAndSupporting(items);
  assert.equal(lead?.headline, "B");
  assert.deepEqual(supporting.map((s) => s.headline), ["A", "C"]);
});

test("pickLeadAndSupporting falls back to the top item when nothing is imminent", () => {
  const items = [ri("recent", "A"), ri("recent", "B")];
  const { lead, supporting } = pickLeadAndSupporting(items);
  assert.equal(lead?.headline, "A");
  assert.deepEqual(supporting.map((s) => s.headline), ["B"]);
});

test("pickLeadAndSupporting handles an empty week", () => {
  assert.deepEqual(pickLeadAndSupporting([]), { lead: null, supporting: [] });
});
