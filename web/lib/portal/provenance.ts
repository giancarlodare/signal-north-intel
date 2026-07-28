// Honest provenance-link labeling (operator rule, 2026-07-28): never imply a
// click lands on the record when it can't. The 2026-07-28 corpus sweep (run
// 30385136530) found three URL shapes in documents.url:
//
//  - RECORD: a real per-item page (the overwhelming majority: every CanadaBuys
//    notice, bids&tenders bid preview, MERX abstract, Biddingo bid page, board
//    PDF, newsroom article).
//  - LISTING: a publisher page that lists many items, carrying a #:~:text=
//    fragment that highlights this item's entry in browsers that support text
//    fragments (Ontario funding opportunities: the publisher offers no
//    per-program pages, so the fragment anchor is the deepest link that
//    exists).
//  - PORTAL: a portal landing page (the bids&tenders guid-missing fallback,
//    11 docs of ~8,000 swept). The member locates the record on the portal by
//    its reference number, so the reference renders beside the link.
export type ProvenanceKind = "record" | "listing" | "portal";

// The two collector fallback shapes when no per-item link existed at capture:
// bids&tenders landing (`.../Module/Tenders/en`) and Biddingo buyer landing
// (`/m/<slug>`). A bare-host URL is a landing page too.
const PORTAL_LANDING = [/\/Module\/Tenders\/en$/, /^\/m\/[^/]+$/];

export function provenanceKind(url: string): ProvenanceKind {
  if (url.includes("#:~:text=")) return "listing";
  try {
    const path = new URL(url).pathname.replace(/\/+$/, "");
    if (path === "" || PORTAL_LANDING.some((re) => re.test(path))) {
      return "portal";
    }
  } catch {
    return "record"; // unparseable: fall through without claiming anything new
  }
  return "record";
}

export function provenanceLabel(kind: ProvenanceKind): string {
  switch (kind) {
    case "record":
      return "View the publisher record →";
    case "listing":
      return "Find on the publisher's page →";
    case "portal":
      return "View on the publisher's portal →";
  }
}
