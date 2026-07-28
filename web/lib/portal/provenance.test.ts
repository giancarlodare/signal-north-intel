// URL shapes verbatim from the 2026-07-28 corpus sweep (run 30385136530).
import { test } from "node:test";
import assert from "node:assert/strict";

import { provenanceKind, provenanceLabel } from "./provenance.ts";

test("real per-item pages label as the record", () => {
  for (const u of [
    "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/ws4576986974",
    "https://peelregion.bidsandtenders.ca/Module/Tenders/en/Tender/Preview/abc-123",
    "https://www.biddingo.com/drps/bid/1/41137979/41228828/verification",
    "https://tpsb.ca/wp-content/uploads/2026/05/minutes.pdf",
  ]) {
    assert.equal(provenanceKind(u), "record", u);
  }
});

test("text-fragment listing anchors label as the publisher's page", () => {
  assert.equal(
    provenanceKind(
      "https://www.ontario.ca/page/available-funding-opportunities-ontario-government#:~:text=Fire%20Protection%20Grant%202026-27",
    ),
    "listing",
  );
});

test("portal landing fallbacks label as the portal", () => {
  for (const u of [
    "https://burlington.bidsandtenders.ca/Module/Tenders/en",
    "https://york.bidsandtenders.ca/Module/Tenders/en/",
    "https://www.biddingo.com/m/drps",
    "https://www.biddingo.com",
  ]) {
    assert.equal(provenanceKind(u), "portal", u);
  }
});

test("labels never over-claim", () => {
  assert.equal(provenanceLabel("record"), "View the publisher record →");
  assert.equal(provenanceLabel("listing"), "Find on the publisher's page →");
  assert.equal(provenanceLabel("portal"), "View on the publisher's portal →");
});
