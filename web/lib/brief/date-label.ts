// Reader-facing date TYPE labels (editorial-model-redesign.md §7.4). A bare date
// is ambiguous: a subscriber could misread an application deadline (future) as a
// past event, so every reader-facing date carries its type. Derived from
// (doc_type, timing_path). This is the single source of truth for the label map.

export type TimingPath = "recent" | "imminent";

const LABELS: Record<string, string> = {
  "grant_program|imminent": "Application deadline",
  "grant_award|imminent": "Application deadline",
  "award_notice|recent": "Contract awarded",
  "tender_notice|imminent": "Tender closes",
  "tender_notice|recent": "Tender expected",
  "board_minutes|recent": "Board decision",
};

// The type label for a reader-facing date. Any combination not in §7.4 gets the
// safe default "Event date" rather than a bare, ambiguous date.
export function dateLabel(
  docType: string | null | undefined,
  timingPath: string | null | undefined,
): string {
  return LABELS[`${docType ?? ""}|${timingPath ?? ""}`] ?? "Event date";
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Format an event date honoring stored precision. Month-precision dates carry a
// day=01 placeholder and MUST render "Apr 2026", never a fabricated full date
// ("None beats a wrong date"). Returns null when there is no parseable date.
export function formatEventDate(
  publishedOn: string | null | undefined,
  precision?: string | null,
): string | null {
  if (!publishedOn) return null;
  const [y, m, d] = publishedOn.slice(0, 10).split("-");
  const mi = Number(m) - 1;
  const day = Number(d);
  if (!/^\d{4}$/.test(y ?? "") || Number.isNaN(mi) || mi < 0 || mi > 11) return null;
  const mon = MONTHS[mi];
  if (precision === "month" || !d || Number.isNaN(day)) return `${mon} ${y}`;
  return `${day} ${mon} ${y}`;
}

// The full reader-facing action window: a type label plus the formatted date,
// e.g. "Tender closes 24 Jul 2026" or "Application deadline Aug 2026". Returns
// null when there is no date to show (we never show a floating label with no
// date, nor a bare date with no label).
export function actionWindow(
  docType: string | null | undefined,
  timingPath: string | null | undefined,
  publishedOn: string | null | undefined,
  precision?: string | null,
): string | null {
  const when = formatEventDate(publishedOn, precision);
  if (!when) return null;
  return `${dateLabel(docType, timingPath)} ${when}`;
}
