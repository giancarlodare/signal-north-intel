import { test } from "node:test";
import assert from "node:assert/strict";
import { renderBrief, renderBriefText, formatCad, type BriefView, type RenderItem } from "./render.ts";

function item(over: Partial<RenderItem> = {}): RenderItem {
  return {
    headline: "Region of Peel tenders SCADA integration",
    timing_path: "imminent",
    vendorSoWhat: "A live integration mandate at a buyer that awards on schedule.",
    buyer: "Region of Peel",
    amountCad: 1_200_000,
    doc: {
      doc_type: "tender_notice",
      url: "https://peelregion.bidsandtenders.ca/x",
      published_on: "2026-07-24",
      date_precision: "day",
    },
    ...over,
  };
}

function view(over: Partial<BriefView> = {}): BriefView {
  return {
    masthead: "The Weekly Signal",
    weekLabel: "14 to 20 July 2026",
    theRead: "Municipal buyers are moving on integration work while the federal side is quiet.",
    lead: item(),
    supporting: [item({ headline: "TPSB benefits administration award", timing_path: "recent",
      doc: { doc_type: "board_minutes", url: "https://tpsb.ca/y", published_on: "2026-04-01",
             date_precision: "month" } })],
    exhibits: [{
      title: "Peel municipal contract awards by quarter",
      basis: "2,758 award notices, Q1 2017 to Q3 2026, source: Peel Region bids&tenders.",
      format: "count",
      rows: [{ label: "Q1 2026", value: 74 }, { label: "Q2 2026", value: 81 },
             { label: "Q3 2026", value: 33, note: "partial" }],
    }],
    reviewedHeldCount: 4,
    methodNote: "Items are selected on event-date timing and a materiality bar.",
    ...over,
  };
}

test("no em dashes anywhere in the rendered brief", () => {
  assert.ok(!renderBrief(view()).includes("—"), "output must contain no em dash");
});

test("every item renders its date TYPE label, never a bare date", () => {
  const html = renderBrief(view());
  assert.ok(html.includes("Tender closes 24 Jul 2026"), "lead action window with label");
  assert.ok(html.includes("Board decision Apr 2026"), "supporting action window with label");
});

test("month-precision date renders the month, never a fabricated day", () => {
  const html = renderBrief(view());
  assert.ok(html.includes("Board decision Apr 2026"));
  assert.ok(!/Board decision \d{1,2} Apr 2026/.test(html), "no fabricated day on a month date");
});

test("every claim carries a provenance link to the publisher document", () => {
  const html = renderBrief(view());
  assert.ok(html.includes('href="https://peelregion.bidsandtenders.ca/x"'));
  assert.ok(html.includes('href="https://tpsb.ca/y"'));
});

test("Watchlist link renders only when a real URL is configured, never a dead one", () => {
  const bare = renderBrief(view());
  assert.ok(!bare.includes("Watchlist"), "no watchlist link without a configured URL");
  const withUrl = renderBrief(view({ watchlistUrl: "https://signalnorthintel.com/watchlist" }));
  assert.ok(withUrl.includes('href="https://signalnorthintel.com/watchlist"'));
  assert.ok(withUrl.includes("Watchlist"));
});

test("a quiet week is stated honestly, not padded", () => {
  const html = renderBrief(view({ lead: null, supporting: [] }));
  assert.ok(html.includes("quiet week"), "quiet-week note present");
  assert.ok(html.includes("do not manufacture items"), "explicit no-padding statement");
  // The standing exhibit still carries substance.
  assert.ok(html.includes("Peel municipal contract awards by quarter"));
});

test("The Read appears and is the editorial lede", () => {
  const html = renderBrief(view());
  assert.ok(html.includes("The Read"));
  assert.ok(html.includes("Municipal buyers are moving on integration work"));
});

test("held-below-bar count is stated for honest density", () => {
  assert.ok(renderBrief(view()).includes("4 further items reviewed"));
  assert.ok(!renderBrief(view({ reviewedHeldCount: 0 })).includes("reviewed this week were held"));
});

test("HTML in copy is escaped (no injection, honest rendering)", () => {
  const html = renderBrief(view({ lead: item({ headline: "A <script> and & sign" }) }));
  assert.ok(html.includes("A &lt;script&gt; and &amp; sign"));
  assert.ok(!html.includes("<script>"));
});

test("formatCad is compact and drops non-positive amounts", () => {
  assert.equal(formatCad(12_400_000), "$12.4M");
  assert.equal(formatCad(622_000), "$622K");
  assert.equal(formatCad(0), null);
  assert.equal(formatCad(null), null);
});

test("plain-text alternative carries the same structure, no em dashes", () => {
  const txt = renderBriefText(view());
  assert.ok(!txt.includes("—"), "no em dash in the text part");
  assert.ok(txt.includes("THE READ"));
  assert.ok(txt.includes("Tender closes 24 Jul 2026"), "type-labeled date in text");
  assert.ok(txt.includes("Source: https://peelregion.bidsandtenders.ca/x"));
  assert.ok(txt.includes("Peel municipal contract awards by quarter".toUpperCase()));
});

test("plain-text states a quiet week honestly", () => {
  const txt = renderBriefText(view({ lead: null, supporting: [] }));
  assert.ok(txt.includes("quiet week"));
  assert.ok(txt.includes("do not manufacture items"));
});
