// Coverage status labels: PUBLIC COMMITMENTS, single-sourced here so the
// homepage register and the member Watching page always agree and there is
// exactly one file to edit when coverage reality changes (operator rule
// 2026-07-27: "opening this year" that does not happen is a broken promise
// on our own site).
//
// OPERATOR-CONFIRMED WORDING ONLY. The first cell states what the record
// holds today (checkable against the live coverage register beside it); the
// expansion cells are forward commitments the operator maintains by hand.
// Do not restore the handoff's "Complete: Ontario policing" wording unless
// coverage genuinely reaches every Ontario service.

export interface CoverageStatusCell {
  label: string;
  text: string;
  tone: "firm" | "faint";
}

export const COVERAGE_STATUS: CoverageStatusCell[] = [
  {
    label: "On the record today",
    text: "The police services, boards, councils and ministries in the register beside this, provincial and federal",
    tone: "firm",
  },
  {
    label: "Expanding",
    text: "Ontario coverage deepens weekly as new buyers clear validation",
    tone: "faint",
  },
  {
    label: "Not yet covered",
    // Operator 2026-07-28: the Ontario Tenders Portal (direct ministry and
    // OPP operational solicitations) forbids automated collection at source
    // (robots), so it is a DISCLOSED boundary, never a claimed coverage.
    // OPP is carried via Infrastructure Ontario capital signal and the
    // provincial agency layer; direct ministry tenders are not collected.
    text: "Direct Ontario ministry tenders (the Ontario Tenders Portal forbids automated collection; OPP carried via capital and agency signal); federal defence procurement; provinces beyond Ontario",
    tone: "faint",
  },
];
