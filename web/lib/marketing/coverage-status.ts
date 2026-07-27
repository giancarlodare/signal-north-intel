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
    text: "Ontario police services, boards and councils in the register beside this, plus provincial programs",
    tone: "firm",
  },
  {
    label: "Expanding",
    text: "Ontario coverage deepens weekly as new buyers clear validation",
    tone: "faint",
  },
  {
    label: "Not yet covered",
    text: "Federal defence procurement; provinces beyond Ontario",
    tone: "faint",
  },
];
