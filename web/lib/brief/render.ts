// Pure, email-safe render of a published brief. No React, no Next, no runtime
// deps: it takes plain data and returns an HTML string, so it is unit-testable
// and is the ONE canonical format shared by the web published view and the
// Resend email (they cannot drift). Inline styles only, table layout, single
// 600px column, system fonts, restrained palette, phone-first. The honesty
// rules are enforced IN the output and asserted in tests: no em dashes, every
// reader-facing date carries its type label, every claim carries a provenance
// link, month-precision dates never fabricate a day, and a thin week is stated
// honestly rather than padded.

import { actionWindow, type TimingPath } from "./date-label.ts";

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
  theRead: string | null;        // the editorial judgment paragraph (brief.intro)
  lead: RenderItem | null;
  supporting: RenderItem[];
  exhibits: Exhibit[];
  reviewedHeldCount: number;     // excluded_below_threshold (honest density)
  methodNote: string;            // selection + provenance method footer
}

const INK = "#1b1b1b";
const MUTE = "#6b6b6b";
const HAIR = "#e4e4e4";
const ACCENT = "#24506b";
const PAPER = "#ffffff";
const SERIF = "Georgia, 'Times New Roman', serif";
const SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

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

function label(text: string): string {
  return `<span style="font-family:${SANS};font-size:11px;letter-spacing:.06em;`
    + `text-transform:uppercase;color:${MUTE};">${esc(text)}</span>`;
}

function itemHtml(it: RenderItem, isLead: boolean): string {
  const window = actionWindow(it.doc.doc_type, it.timing_path,
                              it.doc.published_on, it.doc.date_precision);
  const amount = formatCad(it.amountCad);
  const metaBits = [it.buyer ? esc(it.buyer) : null, amount].filter(Boolean).join("  &middot;  ");
  const headSize = isLead ? "21px" : "17px";
  const rows: string[] = [];

  // Action window with its §7.4 type label (never a bare date).
  if (window) {
    rows.push(`<div style="margin:0 0 6px;">`
      + `<span style="font-family:${SANS};font-size:12px;font-weight:600;`
      + `color:${ACCENT};letter-spacing:.02em;">${esc(window)}</span></div>`);
  }
  // Headline.
  rows.push(`<div style="font-family:${SERIF};font-size:${headSize};line-height:1.3;`
    + `color:${INK};margin:0 0 6px;font-weight:${isLead ? 700 : 600};">${esc(it.headline)}</div>`);
  // Buyer and amount.
  if (metaBits) {
    rows.push(`<div style="font-family:${SANS};font-size:13px;color:${MUTE};margin:0 0 8px;">`
      + `${metaBits}</div>`);
  }
  // The vendor "so what".
  if (it.vendorSoWhat) {
    rows.push(`<div style="font-family:${SERIF};font-size:15px;line-height:1.55;`
      + `color:${INK};margin:0 0 8px;">${esc(it.vendorSoWhat)}</div>`);
  }
  // Provenance link (every claim is sourced to the publisher document).
  if (it.doc.url) {
    rows.push(`<div style="margin:0;">${label("Source")} `
      + `<a href="${esc(it.doc.url)}" style="font-family:${SANS};font-size:12px;`
      + `color:${ACCENT};text-decoration:underline;">publisher record</a></div>`);
  }
  const pad = isLead ? "18px" : "16px";
  const border = isLead ? `border-left:3px solid ${ACCENT};padding-left:15px;` : "";
  return `<div style="padding:${pad} 0;border-top:1px solid ${HAIR};${border}">${rows.join("")}</div>`;
}

function barRow(r: { label: string; value: number; note?: string }, max: number,
                fmt: "count" | "cad"): string {
  const pct = max > 0 ? Math.max(2, Math.round((r.value / max) * 100)) : 0;
  const shown = fmt === "cad" ? (formatCad(r.value) ?? "0") : String(r.value);
  const note = r.note ? ` <span style="color:${MUTE};font-size:11px;">${esc(r.note)}</span>` : "";
  return `<tr>`
    + `<td style="font-family:${SANS};font-size:12px;color:${INK};padding:3px 8px 3px 0;`
    + `white-space:nowrap;vertical-align:middle;">${esc(r.label)}</td>`
    + `<td style="width:100%;vertical-align:middle;padding:3px 0;">`
    + `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><tr>`
    + `<td width="${pct}%" style="background:${ACCENT};height:9px;font-size:0;line-height:0;">&nbsp;</td>`
    + `<td style="font-size:0;line-height:0;">&nbsp;</td></tr></table></td>`
    + `<td style="font-family:${SANS};font-size:12px;color:${INK};padding:3px 0 3px 10px;`
    + `text-align:right;white-space:nowrap;vertical-align:middle;">${esc(shown)}${note}</td>`
    + `</tr>`;
}

function exhibitHtml(ex: Exhibit): string {
  const max = ex.rows.reduce((m, r) => Math.max(m, r.value), 0);
  const bars = ex.rows.map((r) => barRow(r, max, ex.format)).join("");
  return `<div style="padding:18px 0;border-top:1px solid ${HAIR};">`
    + `<div style="font-family:${SANS};font-size:14px;font-weight:600;color:${INK};margin:0 0 3px;">`
    + `${esc(ex.title)}</div>`
    + `<div style="font-family:${SANS};font-size:11px;color:${MUTE};margin:0 0 12px;">${esc(ex.basis)}</div>`
    + `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">`
    + `${bars}</table></div>`;
}

function sectionHead(text: string): string {
  return `<div style="font-family:${SANS};font-size:11px;font-weight:700;`
    + `letter-spacing:.12em;text-transform:uppercase;color:${MUTE};`
    + `margin:26px 0 2px;">${esc(text)}</div>`;
}

export function renderBrief(view: BriefView): string {
  const parts: string[] = [];

  // Masthead.
  parts.push(`<div style="padding:0 0 14px;border-bottom:2px solid ${INK};">`
    + `<div style="font-family:${SERIF};font-size:24px;font-weight:700;color:${INK};`
    + `letter-spacing:-.01em;">${esc(view.masthead)}</div>`
    + `<div style="font-family:${SANS};font-size:12px;color:${MUTE};margin-top:4px;">`
    + `Week of ${esc(view.weekLabel)}</div></div>`);

  // The Read.
  if (view.theRead) {
    parts.push(sectionHead("The Read"));
    parts.push(`<div style="font-family:${SERIF};font-size:16px;line-height:1.6;`
      + `color:${INK};margin:8px 0 4px;">${esc(view.theRead)}</div>`);
  }

  // Lead item.
  if (view.lead) {
    parts.push(sectionHead("Lead"));
    parts.push(itemHtml(view.lead, true));
  }

  // Supporting items, or an honest quiet-week note (never padding).
  if (view.supporting.length > 0) {
    parts.push(sectionHead(view.lead ? "Also this week" : "This week"));
    parts.push(view.supporting.map((it) => itemHtml(it, false)).join(""));
  } else if (!view.lead) {
    parts.push(sectionHead("This week"));
    parts.push(`<div style="font-family:${SERIF};font-size:15px;line-height:1.55;`
      + `color:${INK};padding:14px 0;border-top:1px solid ${HAIR};">`
      + `A quiet week for new signals. The standing exhibits below carry the `
      + `through-line; we do not manufacture items to fill space.</div>`);
  }

  // Standing exhibits.
  if (view.exhibits.length > 0) {
    parts.push(sectionHead("Standing exhibits"));
    parts.push(view.exhibits.map(exhibitHtml).join(""));
  }

  // Provenance / method footer, with the honest held-below-bar count.
  const held = view.reviewedHeldCount > 0
    ? ` ${view.reviewedHeldCount} further item${view.reviewedHeldCount === 1 ? "" : "s"} `
      + `reviewed this week were held below our materiality bar.`
    : "";
  parts.push(`<div style="padding:20px 0 8px;border-top:2px solid ${INK};margin-top:24px;`
    + `font-family:${SANS};font-size:11px;line-height:1.6;color:${MUTE};">`
    + `${esc(view.methodNote)}${esc(held)}</div>`);

  const body = parts.join("");
  const preheader = view.theRead ? esc(view.theRead).slice(0, 140) : `${esc(view.masthead)}`;

  return `<!doctype html><html lang="en"><head><meta charset="utf-8">`
    + `<meta name="viewport" content="width=device-width, initial-scale=1">`
    + `<meta name="color-scheme" content="light only">`
    + `<title>${esc(view.masthead)}</title></head>`
    + `<body style="margin:0;padding:0;background:${PAPER};">`
    + `<div style="display:none;max-height:0;overflow:hidden;opacity:0;">${preheader}</div>`
    + `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" `
    + `style="background:${PAPER};"><tr><td align="center" style="padding:28px 16px;">`
    + `<table role="presentation" width="600" cellpadding="0" cellspacing="0" `
    + `style="width:600px;max-width:600px;background:${PAPER};">`
    + `<tr><td style="padding:0;">${body}</td></tr></table></td></tr></table></body></html>`;
}
