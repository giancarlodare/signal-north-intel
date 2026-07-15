import { test } from "node:test";
import assert from "node:assert/strict";
import { dateLabel, formatEventDate, actionWindow } from "./date-label.ts";

test("dateLabel maps the §7.4 table", () => {
  assert.equal(dateLabel("grant_program", "imminent"), "Application deadline");
  assert.equal(dateLabel("grant_award", "imminent"), "Application deadline");
  assert.equal(dateLabel("award_notice", "recent"), "Contract awarded");
  assert.equal(dateLabel("tender_notice", "imminent"), "Tender closes");
  assert.equal(dateLabel("tender_notice", "recent"), "Tender expected");
  assert.equal(dateLabel("board_minutes", "recent"), "Board decision");
});

test("dateLabel falls back to a safe default, never a bare date", () => {
  assert.equal(dateLabel("news_release", "recent"), "Event date");
  assert.equal(dateLabel(null, null), "Event date");
  assert.equal(dateLabel("grant_program", "recent"), "Event date"); // combo not specified
});

test("formatEventDate honors month precision (never a fabricated day)", () => {
  assert.equal(formatEventDate("2026-04-01", "month"), "Apr 2026");
  assert.equal(formatEventDate("2026-07-24", "day"), "24 Jul 2026");
  assert.equal(formatEventDate("2026-07-24", null), "24 Jul 2026");
});

test("formatEventDate returns null for unparseable input", () => {
  assert.equal(formatEventDate(null), null);
  assert.equal(formatEventDate(""), null);
  assert.equal(formatEventDate("not-a-date"), null);
});

test("actionWindow joins the label and the date, or null with no date", () => {
  assert.equal(actionWindow("tender_notice", "imminent", "2026-07-24", "day"),
               "Tender closes 24 Jul 2026");
  assert.equal(actionWindow("grant_program", "imminent", "2026-08-01", "month"),
               "Application deadline Aug 2026");
  assert.equal(actionWindow("award_notice", "recent", null, null), null);
});
