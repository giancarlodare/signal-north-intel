// Unit tests for the member data layer's pure logic (Wave 3 stage 2). The
// query path runs against RLS in a live DB; here we prove the tag extraction
// and filtering that drive the dashboard.
import { test } from "node:test";
import assert from "node:assert/strict";

import { availableTags, filterItems, type PortalItem } from "./data.ts";

function item(p: Partial<PortalItem>): PortalItem {
  return {
    itemId: p.itemId ?? "i",
    headline: p.headline ?? "h",
    buyer: p.buyer ?? null,
    timingPath: p.timingPath ?? "recent",
    defenceRelevant: p.defenceRelevant ?? false,
    eventDate: p.eventDate ?? null,
    datePrecision: p.datePrecision ?? null,
    docType: p.docType ?? null,
    sourceUrl: p.sourceUrl ?? null,
    vendorSoWhat: p.vendorSoWhat ?? null,
    amountCad: p.amountCad ?? null,
    rank: p.rank ?? 1,
  };
}

const ITEMS: PortalItem[] = [
  item({ itemId: "1", buyer: "Region of Peel", timingPath: "imminent", defenceRelevant: false }),
  item({ itemId: "2", buyer: "City of Toronto", timingPath: "recent", defenceRelevant: true }),
  item({ itemId: "3", buyer: "Region of Peel", timingPath: "recent", defenceRelevant: true }),
  item({ itemId: "4", buyer: null, timingPath: "imminent", defenceRelevant: false }),
];

test("availableTags lists only present values, buyers sorted, null dropped", () => {
  const t = availableTags(ITEMS);
  assert.deepEqual(t.buyers, ["City of Toronto", "Region of Peel"]);
  assert.deepEqual([...t.timings].sort(), ["imminent", "recent"]);
  assert.equal(t.hasDefence, true);
});

test("availableTags reports no defence when none present", () => {
  const t = availableTags([item({ defenceRelevant: false })]);
  assert.equal(t.hasDefence, false);
});

test("filterItems by buyer", () => {
  const r = filterItems(ITEMS, { buyer: "Region of Peel" });
  assert.deepEqual(r.map((i) => i.itemId), ["1", "3"]);
});

test("filterItems by timing", () => {
  const r = filterItems(ITEMS, { timing: "imminent" });
  assert.deepEqual(r.map((i) => i.itemId), ["1", "4"]);
});

test("filterItems defenceOnly", () => {
  const r = filterItems(ITEMS, { defenceOnly: true });
  assert.deepEqual(r.map((i) => i.itemId), ["2", "3"]);
});

test("filterItems combines predicates (AND)", () => {
  const r = filterItems(ITEMS, { buyer: "Region of Peel", defenceOnly: true, timing: "recent" });
  assert.deepEqual(r.map((i) => i.itemId), ["3"]);
});

test("filterItems with no filter returns all", () => {
  assert.equal(filterItems(ITEMS, {}).length, 4);
});
