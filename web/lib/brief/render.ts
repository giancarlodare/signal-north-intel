// Pure, email-safe render of a published brief. No React, no Next, no runtime
// deps: it takes plain data and returns an HTML string, so it is unit-testable
// and is the ONE canonical format shared by the web published view and the
// Resend email (they cannot drift). Layout is the designed Weekly Signal
// template (operator-supplied, 2026-07-20): navy masthead and footer, cream
// Read band, crimson lead card, buyer-grouped item list, framed standing
// exhibit. Table layout, inline styles, single 600px column, email-client
// fonts (Georgia/Arial/Courier). The honesty rules are enforced IN the output
// and asserted in tests: no em dashes, every reader-facing date carries its
// type label, every claim carries a provenance link, month-precision dates
// never fabricate a day, and a thin week is stated honestly rather than padded.

import { actionWindow, dateLabel, formatEventDate, type TimingPath } from "./date-label.ts";

export interface BriefDoc {
  doc_type: string | null;
  url: string | null;
  published_on: string | null;
  date_precision: string | null;
}
export interface RenderItem {
  headline: string;
  timing_path: TimingPath;
  vendorSoWhat: string | null;   // the "so what for a vendor" (editor_note)
  buyer: string | null;
  amountCad: number | null;
  doc: BriefDoc;
}
export interface Exhibit {
  title: string;
  basis: string;                 // data basis: record count, range, sources
  format: "count" | "cad";
  rows: { label: string; value: number; note?: string }[];
}
export interface BriefView {
  masthead: string;              // "The Weekly Signal"
  weekLabel: string;             // e.g. "14 to 20 July 2026"
  weekStart?: string | null;     // ISO week_start date; drives the derived issue tag
  theRead: string | null;        // the editorial judgment paragraph (brief.intro)
  lead: RenderItem | null;
  supporting: RenderItem[];
  exhibits: Exhibit[];
  reviewedHeldCount: number;     // excluded_below_threshold (honest density)
  methodNote: string;            // selection + provenance method footer
  // The design reserves a per-item "Watchlist" action ({{WATCH_URL}}). No
  // watchlist feature exists yet, so the link renders ONLY when a real URL is
  // supplied here; a dead placeholder link is never emitted.
  watchlistUrl?: string | null;
}

// Designed palette (from the supplied template).
const NAVY = "#0d1b2e";
const NAVY_RULE = "#243d5c";
const CRIMSON = "#c41230";
const PAPER = "#ffffff";
const CREAM = "#f8f7f4";
const PAGE = "#f3f2ef";
const BORDER = "#d4d1cb";
const BODY = "#4a4742";
const MUTED = "#9a948a";
const SERIF = "Georgia, 'Times New Roman', serif";
const SANS = "Arial, Helvetica, sans-serif";
const MONO = "'Courier New', Courier, monospace";

function esc(s: string | null | undefined): string {
  return (s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));
}

// Compact CAD for a memo: $12.4M, $622K, else the plain dollar amount.
export function formatCad(n: number | null | undefined): string | null {
  if (n == null || !Number.isFinite(n) || n <= 0) return null;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
}

// The masthead's top-right tag. The design shows an issue number; we do not
// keep a fabricatable sequence counter, so the tag is the ISO week DERIVED
// from week_start (factual, deterministic). No week_start, no tag.
export function isoWeekTag(weekStart: string | null | undefined): string | null {
  if (!weekStart) return null;
  const d = new Date(`${weekStart.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return null;
  const t = new Date(d);
  t.setUTCDate(t.getUTCDate() + 3 - ((t.getUTCDay() + 6) % 7)); // ISO: the week's Thursday
  const jan4 = new Date(Date.UTC(t.getUTCFullYear(), 0, 4));
  jan4.setUTCDate(jan4.getUTCDate() + 3 - ((jan4.getUTCDay() + 6) % 7));
  const week = 1 + Math.round((t.getTime() - jan4.getTime()) / (7 * 86400000));
  return `WK ${String(week).padStart(2, "0")} / ${t.getUTCFullYear()}`;
}

// The action window as HTML for a narrow date cell: the label may wrap onto
// its own line, but the date's internal spaces are non-breaking so it can
// never split mid-date ("Tender expected 16 / Jul 2026" on a phone render).
function actionWindowHtml(it: RenderItem): string | null {
  const when = formatEventDate(it.doc.published_on, it.doc.date_precision);
  if (!when) return null;
  return `${esc(dateLabel(it.doc.doc_type, it.timing_path))} ${esc(when).replace(/ /g, "&nbsp;")}`;
}

const KICKER = `font-family:${SANS};font-size:11px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;mso-line-height-rule:exactly;line-height:16px;`;
const DATE_CELL = `font-family:${MONO};font-size:12px;color:${BODY};mso-line-height-rule:exactly;line-height:24px;`;
// Phone-first type floors (operator, 2026-07-20): body text 16px minimum,
// item notes 15px minimum, with comfortable line-height. Small type in email
// gets silently ignored on a phone.
const NOTE_TEXT = `font-family:${SANS};font-size:15px;color:${BODY};mso-line-height-rule:exactly;line-height:24px;`;
const BODY_TEXT = `font-family:${SANS};font-size:16px;color:${BODY};mso-line-height-rule:exactly;line-height:26px;`;

function spacer(h: number): string {
  return `<tr><td colspan="2" height="${h}" style="font-size:1px;line-height:1px;">&nbsp;</td></tr>`;
}

// A full-width band row of the 600px wrapper. White bands carry the side rule.
function band(body: string, bg: string, pad: string, ruled = true): string {
  const sides = ruled ? `border-left:1px solid ${BORDER};border-right:1px solid ${BORDER};` : "";
  return `<tr><td bgcolor="${bg}" style="background-color:${bg};padding:${pad};${sides}">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="512" style="width:100%;">`
    + `${body}</table></td></tr>`;
}

function mastheadHtml(view: BriefView): string {
  const tag = isoWeekTag(view.weekStart);
  const rows = [
    `<tr><td align="left" style="${KICKER}color:${CRIMSON};">Procurement Intelligence Brief</td>`
    + `<td align="right" style="font-family:${MONO};font-size:12px;color:${MUTED};`
    + `mso-line-height-rule:exactly;line-height:16px;">${tag ? esc(tag) : "&nbsp;"}</td></tr>`,
    spacer(14),
    `<tr><td colspan="2" align="left" style="font-family:${SERIF};font-size:34px;font-weight:normal;`
    + `color:#ffffff;letter-spacing:-0.5px;mso-line-height-rule:exactly;line-height:40px;">`
    + `${esc(view.masthead)}</td></tr>`,
    spacer(12),
    `<tr><td colspan="2" style="border-top:1px solid ${NAVY_RULE};padding-top:12px;`
    + `font-family:${SANS};font-size:12px;letter-spacing:1px;color:${MUTED};text-transform:uppercase;`
    + `mso-line-height-rule:exactly;line-height:18px;">Week of ${esc(view.weekLabel)}</td></tr>`,
  ];
  return band(rows.join(""), NAVY, "36px 44px 32px 44px", false);
}

function readHtml(view: BriefView): string {
  if (!view.theRead) return "";
  const rows = [
    `<tr><td style="${KICKER}color:${NAVY};padding-bottom:16px;">The Read</td></tr>`,
    `<tr><td style="font-family:${SERIF};font-size:17px;color:${NAVY};`
    + `mso-line-height-rule:exactly;line-height:28px;">${esc(view.theRead)}</td></tr>`,
  ];
  return band(rows.join(""), CREAM, "36px 44px");
}

// Provenance link. Every claim carries one where the publisher document has a
// public URL; nothing is linked to a URL we do not hold.
function sourceLink(url: string | null, labelText: string): string {
  if (!url) return "";
  return `<a href="${esc(url)}" style="color:${CRIMSON};text-decoration:none;">${esc(labelText)}</a>`;
}

const SRC_CELL = `font-family:${SANS};font-size:12px;font-weight:bold;letter-spacing:1px;`
  + `text-transform:uppercase;mso-line-height-rule:exactly;line-height:18px;`;

// Right-aligned Watchlist action cell; empty (not a dead link) until a real
// watchlist URL exists.
function watchCell(view: BriefView, padTop = ""): string {
  const inner = view.watchlistUrl
    ? `<a href="${esc(view.watchlistUrl)}" style="color:${MUTED};text-decoration:none;">`
      + `&#9873;&nbsp;&nbsp;Watchlist</a>`
    : "&nbsp;";
  return `<td align="right" style="${padTop}font-family:${SANS};font-size:12px;`
    + `mso-line-height-rule:exactly;line-height:18px;white-space:nowrap;">${inner}</td>`;
}

function leadHtml(view: BriefView): string {
  const it = view.lead;
  if (!it) return "";
  const window = actionWindowHtml(it);
  const meta = [it.buyer ? esc(it.buyer) : null, formatCad(it.amountCad)]
    .filter(Boolean).join(" &middot; ");
  const inner: string[] = [
    `<tr><td align="left" style="${KICKER}color:${CRIMSON};">Lead Item</td>`
    + `<td align="right" style="font-family:${MONO};font-size:12px;color:${BODY};`
    + `mso-line-height-rule:exactly;line-height:16px;">${window ?? "&nbsp;"}</td></tr>`,
    spacer(14),
    `<tr><td colspan="2" style="font-family:${SERIF};font-size:22px;color:${NAVY};`
    + `mso-line-height-rule:exactly;line-height:29px;">${esc(it.headline)}</td></tr>`,
  ];
  if (meta) {
    inner.push(spacer(8));
    inner.push(`<tr><td colspan="2" style="font-family:${SANS};font-size:12px;color:${MUTED};`
      + `mso-line-height-rule:exactly;line-height:18px;">${meta}</td></tr>`);
  }
  if (it.vendorSoWhat) {
    inner.push(spacer(12));
    inner.push(`<tr><td colspan="2" style="${BODY_TEXT}">${esc(it.vendorSoWhat)}</td></tr>`);
  }
  if (it.doc.url) {
    inner.push(spacer(16));
    inner.push(`<tr><td colspan="2" style="${SRC_CELL}">`
      + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="454" style="width:100%;">`
      + `<tr><td align="left" style="${SRC_CELL}">${sourceLink(it.doc.url, "View the publisher record")}</td>`
      + `${watchCell(view)}</tr></table></td></tr>`);
  }
  const card = `<tr><td style="border-top:3px solid ${CRIMSON};">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="512" `
    + `style="width:100%;border:1px solid ${BORDER};border-top:none;"><tr><td style="padding:28px 28px 26px 28px;">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="454" style="width:100%;">`
    + `${inner.join("")}</table></td></tr></table></td></tr>`;
  return band(card, PAPER, "36px 44px 8px 44px");
}

// Supporting items in rank order, grouped visually under buyer headings per the
// operator's ruling: separate brief items with separate dates and notes, one
// heading per buyer in order of that buyer's strongest (first-ranked) item.
export function groupByBuyer(items: RenderItem[]): { buyer: string | null; items: RenderItem[] }[] {
  const order: (string | null)[] = [];
  const byBuyer = new Map<string | null, RenderItem[]>();
  for (const it of items) {
    const key = it.buyer ?? null;
    if (!byBuyer.has(key)) { byBuyer.set(key, []); order.push(key); }
    byBuyer.get(key)!.push(it);
  }
  return order.map((b) => ({ buyer: b, items: byBuyer.get(b)! }));
}

function itemRow(it: RenderItem, view: BriefView): string {
  const window = actionWindowHtml(it);
  const noteRow = it.vendorSoWhat
    ? `<tr><td colspan="2" style="padding-top:8px;${NOTE_TEXT}">${esc(it.vendorSoWhat)}</td></tr>`
    : "";
  // Source sits on its own row (left), with the Watchlist action opposite.
  const srcRow = it.doc.url
    ? `<tr><td align="left" style="padding-top:10px;${SRC_CELL}">`
      + `${sourceLink(it.doc.url, "Source")}</td>${watchCell(view, "padding-top:10px;")}</tr>`
    : "";
  return `<tr><td style="padding:20px 0 22px 0;border-bottom:1px solid ${BORDER};">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="512" style="width:100%;">`
    + `<tr><td align="left" style="font-family:${SERIF};font-size:17px;color:${NAVY};`
    + `mso-line-height-rule:exactly;line-height:24px;">${esc(it.headline)}</td>`
    + `<td align="right" valign="top" width="150" style="width:150px;${DATE_CELL}">`
    + `${window ?? "&nbsp;"}</td></tr>`
    + `${noteRow}${srcRow}</table></td></tr>`;
}

function buyerHeading(buyer: string | null): string {
  return `<tr><td style="padding:20px 0 4px 0;border-bottom:1px solid ${NAVY};`
    + `${KICKER}font-size:12px;color:${NAVY};line-height:18px;">`
    + `${esc(buyer ?? "Buyer unresolved")}</td></tr>`;
}

function itemsHtml(view: BriefView): string {
  if (view.supporting.length > 0) {
    const groups = groupByBuyer(view.supporting);
    const rows = groups.map((g) =>
      buyerHeading(g.buyer) + g.items.map((it) => itemRow(it, view)).join("")).join("");
    return band(rows, PAPER, "32px 44px 12px 44px");
  }
  if (!view.lead) {
    // A quiet week is stated honestly, never padded.
    const rows = `<tr><td style="padding:20px 0 22px 0;font-family:${SERIF};font-size:16px;`
      + `color:${NAVY};mso-line-height-rule:exactly;line-height:26px;">`
      + `A quiet week for new signals. The standing exhibits below carry the `
      + `through-line; we do not manufacture items to fill space.</td></tr>`;
    return band(rows, PAPER, "32px 44px 12px 44px");
  }
  return "";
}

// Exhibit bars per the template geometry: 300px track, px = value/max * 300,
// 4px floor so zero-adjacent values stay visible. Counts and CAD both honest;
// the "partial" note rides the label so a part-quarter is never a full bar lie.
function exhibitRow(r: { label: string; value: number; note?: string }, max: number,
                    fmt: "count" | "cad"): string {
  const px = max > 0 ? Math.max(4, Math.round((r.value / max) * 300)) : 4;
  const shown = fmt === "cad" ? (formatCad(r.value) ?? "0") : String(r.value);
  const labelText = r.note ? `${r.label} (${r.note})` : r.label;
  return `<tr><td style="padding:0 0 12px 0;">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="454" style="width:100%;">`
    + `<tr><td width="104" style="width:104px;font-family:${SANS};font-size:12px;color:${BODY};`
    + `mso-line-height-rule:exactly;line-height:16px;padding-right:10px;">${esc(labelText)}</td>`
    + `<td width="300" style="width:300px;" valign="middle">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>`
    + `<td width="${px}" height="14" bgcolor="${NAVY}" style="width:${px}px;height:14px;`
    + `background-color:${NAVY};font-size:1px;line-height:1px;">&nbsp;</td></tr></table></td>`
    + `<td align="right" style="font-family:${MONO};font-size:12px;color:${NAVY};`
    + `mso-line-height-rule:exactly;line-height:16px;padding-left:10px;white-space:nowrap;">`
    + `${esc(shown)}</td></tr></table></td></tr>`;
}

function exhibitHtml(ex: Exhibit): string {
  const max = ex.rows.reduce((m, r) => Math.max(m, r.value), 0);
  const bars = ex.rows.map((r) => exhibitRow(r, max, ex.format)).join("");
  const card = `<tr><td style="padding:0;">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="512" `
    + `style="width:100%;border:1px solid ${BORDER};" bgcolor="${CREAM}">`
    + `<tr><td style="padding:26px 28px 28px 28px;background-color:${CREAM};">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="454" style="width:100%;">`
    + `<tr><td style="${KICKER}color:${NAVY};">Standing Exhibit</td></tr>`
    + `<tr><td style="padding:6px 0 18px 0;font-family:${SERIF};font-size:17px;color:${NAVY};`
    + `mso-line-height-rule:exactly;line-height:24px;">${esc(ex.title)}</td></tr>`
    + `${bars}`
    + `<tr><td style="padding-top:8px;border-top:1px solid ${BORDER};font-family:${SANS};`
    + `font-size:11px;color:${MUTED};mso-line-height-rule:exactly;line-height:16px;">`
    + `${esc(ex.basis)}</td></tr>`
    + `</table></td></tr></table></td></tr>`;
  return band(card, PAPER, "28px 44px 40px 44px");
}

function footerHtml(view: BriefView): string {
  // Honest density: the held-below-bar count is part of the methodology, so a
  // thin brief can never masquerade as the whole week's activity.
  const held = view.reviewedHeldCount > 0
    ? ` ${view.reviewedHeldCount} further item${view.reviewedHeldCount === 1 ? "" : "s"} `
      + `reviewed this week were held below our materiality bar.`
    : "";
  // Pre-gate footer: the brief goes to the operator only, so there is no
  // subscriber boilerplate. A postal address and a real unsubscribe link
  // (CASL / CAN-SPAM) MUST be added here before any real subscriber send;
  // fabricated placeholders are worse than their absence.
  const rows = [
    `<tr><td style="${KICKER}color:${MUTED};padding-bottom:12px;">Methodology</td></tr>`,
    `<tr><td style="font-family:${SANS};font-size:12px;color:${MUTED};`
    + `mso-line-height-rule:exactly;line-height:19px;padding-bottom:24px;">`
    + `${esc(view.methodNote)}${esc(held)}</td></tr>`,
    `<tr><td style="border-top:1px solid ${NAVY_RULE};padding-top:20px;font-family:${SANS};`
    + `font-size:11px;color:${MUTED};mso-line-height-rule:exactly;line-height:18px;">`
    + `${esc(view.masthead)} &#183; signalnorthintel.com</td></tr>`,
  ];
  return band(rows.join(""), NAVY, "32px 44px 36px 44px", false);
}

export function renderBrief(view: BriefView): string {
  const bands = [
    mastheadHtml(view),
    readHtml(view),
    leadHtml(view),
    itemsHtml(view),
    view.exhibits.map(exhibitHtml).join(""),
    footerHtml(view),
  ].join("");
  return renderShell(view, bands);
}

// Plain-text alternative part, from the same data, so a client that prefers
// text (or a screen reader) gets an ordered, labeled document, not raw HTML.
export function renderBriefText(view: BriefView): string {
  const L: string[] = [view.masthead.toUpperCase(), `Week of ${view.weekLabel}`, ""];
  const itemText = (it: RenderItem): string => {
    const win = actionWindow(it.doc.doc_type, it.timing_path, it.doc.published_on, it.doc.date_precision);
    const bits = [it.buyer, formatCad(it.amountCad)].filter(Boolean).join("  |  ");
    const lines: string[] = [];
    if (win) lines.push(win);
    lines.push(it.headline);
    if (bits) lines.push(bits);
    if (it.vendorSoWhat) lines.push(it.vendorSoWhat);
    if (it.doc.url) lines.push(`Source: ${it.doc.url}`);
    return lines.join("\n");
  };
  if (view.theRead) L.push("THE READ", view.theRead, "");
  if (view.lead) L.push("LEAD", itemText(view.lead), "");
  if (view.supporting.length > 0) {
    L.push(view.lead ? "ALSO THIS WEEK" : "THIS WEEK");
    for (const it of view.supporting) L.push(itemText(it), "");
  } else if (!view.lead) {
    L.push("THIS WEEK",
      "A quiet week for new signals. The standing exhibits carry the through-line; "
      + "we do not manufacture items to fill space.", "");
  }
  for (const ex of view.exhibits) {
    L.push(ex.title.toUpperCase(), ex.basis);
    for (const r of ex.rows) {
      const v = ex.format === "cad" ? (formatCad(r.value) ?? "0") : String(r.value);
      L.push(`  ${r.label}: ${v}${r.note ? ` (${r.note})` : ""}`);
    }
    L.push("");
  }
  const held = view.reviewedHeldCount > 0
    ? ` ${view.reviewedHeldCount} further item${view.reviewedHeldCount === 1 ? "" : "s"} `
      + "reviewed this week were held below our materiality bar."
    : "";
  L.push(view.methodNote + held);
  return L.join("\n");
}

function renderShell(view: BriefView, bands: string): string {
  const preheader = view.theRead ? esc(view.theRead).slice(0, 140) : esc(view.masthead);
  return `<!DOCTYPE html><html lang="en" xmlns="http://www.w3.org/1999/xhtml" `
    + `xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head>`
    + `<meta charset="utf-8">`
    + `<meta name="viewport" content="width=device-width, initial-scale=1.0">`
    + `<meta name="color-scheme" content="light dark">`
    + `<meta name="supported-color-schemes" content="light dark">`
    + `<!--[if mso]><noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch>`
    + `</o:OfficeDocumentSettings></xml></noscript><![endif]-->`
    + `<title>${esc(view.masthead)}</title></head>`
    + `<body style="margin:0;padding:0;background-color:${PAGE};`
    + `-webkit-text-size-adjust:100%;text-size-adjust:100%;">`
    + `<span style="display:none;font-size:1px;color:${PAGE};line-height:1px;max-height:0;`
    + `max-width:0;opacity:0;overflow:hidden;mso-hide:all;">${preheader}</span>`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" `
    + `style="background-color:${PAGE};"><tr><td align="center" style="padding:32px 12px;">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" `
    + `style="width:600px;max-width:600px;">${bands}</table>`
    + `</td></tr></table></body></html>`;
}
