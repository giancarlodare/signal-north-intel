#!/usr/bin/env node
/**
 * Shadow-brief preview send (operator 2026-08-08).
 *
 * Reads brief_preview.json (written by brief_generator.py --preview-json),
 * renders it with the canonical Weekly Signal template, and sends it via
 * Resend to BRIEF_PREVIEW_TO (default: giancarlodare@gmail.com) ONLY.
 * No database reads or writes. The operator reviews it in a real client
 * before approving the DB-write run.
 *
 * Usage:
 *   RESEND_API_KEY=... node web/scripts/send-brief-preview.mjs [path/to/brief_preview.json]
 *
 * Env vars:
 *   RESEND_API_KEY       required -- ci-preview scoped key
 *   BRIEF_PREVIEW_TO     recipient (default: giancarlodare@gmail.com)
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// date-label.ts port
// ---------------------------------------------------------------------------

const DATE_LABELS = {
  "grant_program|imminent": "Application deadline",
  "grant_award|imminent":   "Application deadline",
  "award_notice|recent":    "Contract awarded",
  "tender_notice|imminent": "Tender closes",
  "tender_notice|recent":   "Bids closed",
  "board_minutes|recent":   "Board decision",
};

function dateLabel(docType, timingPath) {
  return DATE_LABELS[`${docType ?? ""}|${timingPath ?? ""}`] ?? "Event date";
}

const MONTHS_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function formatEventDate(publishedOn, precision) {
  if (!publishedOn) return null;
  const [y, m, d] = publishedOn.slice(0, 10).split("-");
  const mi = Number(m) - 1;
  const day = Number(d);
  if (!/^\d{4}$/.test(y ?? "") || Number.isNaN(mi) || mi < 0 || mi > 11) return null;
  const mon = MONTHS_SHORT[mi];
  if (precision === "month" || !d || Number.isNaN(day)) return `${mon} ${y}`;
  return `${day} ${mon} ${y}`;
}

function actionWindowText(docType, timingPath, publishedOn, precision) {
  const when = formatEventDate(publishedOn, precision);
  if (!when) return null;
  return `${dateLabel(docType, timingPath)} ${when}`;
}

// ---------------------------------------------------------------------------
// view.ts helpers port
// ---------------------------------------------------------------------------

const MONTHS_FULL = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];

function weekLabel(weekStart) {
  const s = new Date(`${(weekStart ?? "").slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(s.getTime())) return weekStart;
  const e = new Date(s);
  e.setUTCDate(e.getUTCDate() + 6);
  const sd = s.getUTCDate(), ed = e.getUTCDate();
  const sm = s.getUTCMonth(),  em = e.getUTCMonth();
  const sy = s.getUTCFullYear(), ey = e.getUTCFullYear();
  if (sy !== ey) return `${sd} ${MONTHS_FULL[sm]} ${sy} to ${ed} ${MONTHS_FULL[em]} ${ey}`;
  if (sm !== em) return `${sd} ${MONTHS_FULL[sm]} to ${ed} ${MONTHS_FULL[em]} ${ey}`;
  return `${sd} to ${ed} ${MONTHS_FULL[em]} ${ey}`;
}

function pickLeadAndSupporting(items) {
  if (items.length === 0) return { lead: null, supporting: [] };
  let li = items.findIndex((it) => it.timing_path === "imminent");
  if (li < 0) li = 0;
  return { lead: items[li], supporting: items.filter((_, i) => i !== li) };
}

function deepLink(url, publisherTitle) {
  if (!url) return null;
  if (url.includes("#")) return url;
  const words = (publisherTitle ?? "").trim().split(/\s+/).slice(0, 8).join(" ");
  if (words.length < 12) return url;
  return url + "#:~:text=" + encodeURIComponent(words).replace(/-/g, "%2D");
}

// ---------------------------------------------------------------------------
// render.ts port
// ---------------------------------------------------------------------------

const NAVY      = "#0d1b2e";
const NAVY_RULE = "#243d5c";
const CRIMSON   = "#c41230";
const PAPER     = "#ffffff";
const CREAM     = "#f8f7f4";
const PAGE      = "#f3f2ef";
const BORDER    = "#d4d1cb";
const BODY_CLR  = "#4a4742";
const MUTED     = "#9a948a";
const SERIF     = "Georgia, 'Times New Roman', serif";
const SANS      = "Arial, Helvetica, sans-serif";
const MONO      = "'Courier New', Courier, monospace";

function esc(s) {
  return (s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function formatCad(n) {
  if (n == null || !Number.isFinite(n) || n <= 0) return null;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
}

function isoWeekTag(weekStart) {
  if (!weekStart) return null;
  const d = new Date(`${weekStart.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return null;
  const t = new Date(d);
  t.setUTCDate(t.getUTCDate() + 3 - ((t.getUTCDay() + 6) % 7));
  const jan4 = new Date(Date.UTC(t.getUTCFullYear(), 0, 4));
  jan4.setUTCDate(jan4.getUTCDate() + 3 - ((jan4.getUTCDay() + 6) % 7));
  const week = 1 + Math.round((t.getTime() - jan4.getTime()) / (7 * 86400000));
  return `WK ${String(week).padStart(2, "0")} / ${t.getUTCFullYear()}`;
}

function actionWindowHtml(it) {
  const when = formatEventDate(it.doc.published_on, it.doc.date_precision);
  if (!when) return null;
  return `${esc(dateLabel(it.doc.doc_type, it.timing_path))} ${esc(when).replace(/ /g, "&nbsp;")}`;
}

const KICKER    = `font-family:${SANS};font-size:11px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;mso-line-height-rule:exactly;line-height:16px;`;
const DATE_CELL = `font-family:${MONO};font-size:12px;color:${BODY_CLR};mso-line-height-rule:exactly;line-height:24px;`;
const NOTE_TEXT = `font-family:${SANS};font-size:15px;color:${BODY_CLR};mso-line-height-rule:exactly;line-height:24px;`;
const BODY_TEXT = `font-family:${SANS};font-size:16px;color:${BODY_CLR};mso-line-height-rule:exactly;line-height:26px;`;
const SRC_CELL  = `font-family:${SANS};font-size:12px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;mso-line-height-rule:exactly;line-height:18px;`;

function spacer(h) {
  return `<tr><td colspan="2" height="${h}" style="font-size:1px;line-height:1px;">&nbsp;</td></tr>`;
}

function band(body, bg, pad, ruled = true) {
  const sides = ruled ? `border-left:1px solid ${BORDER};border-right:1px solid ${BORDER};` : "";
  return `<tr><td class="sn-pad" bgcolor="${bg}" style="background-color:${bg};padding:${pad};${sides}">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="512" style="width:100%;">`
    + `${body}</table></td></tr>`;
}

function sourceLink(url, labelText) {
  if (!url) return "";
  return `<a href="${esc(url)}" style="color:${CRIMSON};text-decoration:none;">${esc(labelText)}</a>`;
}

function watchCell(view, padTop = "") {
  const inner = view.watchlistUrl
    ? `<a href="${esc(view.watchlistUrl)}" style="color:${MUTED};text-decoration:none;">&#9873;&nbsp;&nbsp;Watchlist</a>`
    : "&nbsp;";
  return `<td align="right" style="${padTop}font-family:${SANS};font-size:12px;mso-line-height-rule:exactly;line-height:18px;white-space:nowrap;">${inner}</td>`;
}

function mastheadHtml(view) {
  const tag = isoWeekTag(view.weekStart);
  const rows = [
    `<tr><td align="left" style="${KICKER}color:${CRIMSON};">Procurement Intelligence Brief</td>`
    + `<td align="right" style="font-family:${MONO};font-size:12px;color:${MUTED};mso-line-height-rule:exactly;line-height:16px;">${tag ? esc(tag) : "&nbsp;"}</td></tr>`,
    spacer(14),
    `<tr><td colspan="2" align="left" style="font-family:${SERIF};font-size:34px;font-weight:normal;color:#ffffff;letter-spacing:-0.5px;mso-line-height-rule:exactly;line-height:40px;">${esc(view.masthead)}</td></tr>`,
    spacer(12),
    `<tr><td colspan="2" style="border-top:1px solid ${NAVY_RULE};padding-top:12px;font-family:${SANS};font-size:12px;letter-spacing:1px;color:${MUTED};text-transform:uppercase;mso-line-height-rule:exactly;line-height:18px;">Week of ${esc(view.weekLabel)}</td></tr>`,
  ];
  return band(rows.join(""), NAVY, "36px 44px 32px 44px", false);
}

function readHtml(view) {
  if (!view.theRead) return "";
  const rows = [
    `<tr><td style="${KICKER}color:${NAVY};padding-bottom:16px;">The Read</td></tr>`,
    `<tr><td style="font-family:${SERIF};font-size:17px;color:${NAVY};mso-line-height-rule:exactly;line-height:28px;">${esc(view.theRead)}</td></tr>`,
  ];
  return band(rows.join(""), CREAM, "36px 44px");
}

function leadHtml(view) {
  const it = view.lead;
  if (!it) return "";
  const window = actionWindowHtml(it);
  const meta = [it.buyer ? esc(it.buyer) : null, formatCad(it.amountCad)].filter(Boolean).join(" &middot; ");
  const inner = [
    `<tr><td align="left" style="${KICKER}color:${CRIMSON};">Lead Item</td>`
    + `<td align="right" style="font-family:${MONO};font-size:12px;color:${BODY_CLR};mso-line-height-rule:exactly;line-height:16px;">${window ?? "&nbsp;"}</td></tr>`,
    spacer(14),
    `<tr><td colspan="2" style="font-family:${SERIF};font-size:22px;color:${NAVY};mso-line-height-rule:exactly;line-height:29px;">${esc(it.headline)}</td></tr>`,
  ];
  if (meta) {
    inner.push(spacer(8));
    inner.push(`<tr><td colspan="2" style="font-family:${SANS};font-size:12px;color:${MUTED};mso-line-height-rule:exactly;line-height:18px;">${meta}</td></tr>`);
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
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="512" style="width:100%;border:1px solid ${BORDER};border-top:none;"><tr><td style="padding:28px 28px 26px 28px;">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="454" style="width:100%;">`
    + `${inner.join("")}</table></td></tr></table></td></tr>`;
  return band(card, PAPER, "36px 44px 8px 44px");
}

function groupByBuyer(items) {
  const order = [];
  const byBuyer = new Map();
  for (const it of items) {
    const key = it.buyer ?? null;
    if (!byBuyer.has(key)) { byBuyer.set(key, []); order.push(key); }
    byBuyer.get(key).push(it);
  }
  return order.map((b) => ({ buyer: b, items: byBuyer.get(b) }));
}

function itemRow(it, view) {
  const window = actionWindowHtml(it);
  const noteRow = it.vendorSoWhat
    ? `<tr><td colspan="2" style="padding-top:8px;${NOTE_TEXT}">${esc(it.vendorSoWhat)}</td></tr>`
    : "";
  const srcRow = it.doc.url
    ? `<tr><td align="left" style="padding-top:10px;${SRC_CELL}">${sourceLink(it.doc.url, "Source")}</td>${watchCell(view, "padding-top:10px;")}</tr>`
    : "";
  return `<tr><td style="padding:20px 0 22px 0;border-bottom:1px solid ${BORDER};">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="512" style="width:100%;">`
    + `<tr><td align="left" style="font-family:${SERIF};font-size:17px;color:${NAVY};mso-line-height-rule:exactly;line-height:24px;">${esc(it.headline)}</td>`
    + `<td align="right" valign="top" width="150" style="width:150px;${DATE_CELL}">${window ?? "&nbsp;"}</td></tr>`
    + `${noteRow}${srcRow}</table></td></tr>`;
}

function buyerHeading(buyer) {
  return `<tr><td style="padding:20px 0 4px 0;border-bottom:1px solid ${NAVY};${KICKER}font-size:12px;color:${NAVY};line-height:18px;">${esc(buyer ?? "Buyer unresolved")}</td></tr>`;
}

function itemsHtml(view) {
  if (view.supporting.length > 0) {
    const groups = groupByBuyer(view.supporting);
    const rows = groups.map((g) => buyerHeading(g.buyer) + g.items.map((it) => itemRow(it, view)).join("")).join("");
    return band(rows, PAPER, "32px 44px 12px 44px");
  }
  if (!view.lead) {
    const rows = `<tr><td style="padding:20px 0 22px 0;font-family:${SERIF};font-size:16px;color:${NAVY};mso-line-height-rule:exactly;line-height:26px;">A quiet week for new signals. We report what the record holds and do not manufacture items to fill space.</td></tr>`;
    return band(rows, PAPER, "32px 44px 12px 44px");
  }
  return "";
}

function footerHtml(view) {
  const held = view.reviewedHeldCount > 0
    ? ` ${view.reviewedHeldCount} further item${view.reviewedHeldCount === 1 ? "" : "s"} reviewed this week were held below our materiality bar.`
    : "";
  const rows = [
    `<tr><td style="${KICKER}color:${MUTED};padding-bottom:12px;">Methodology</td></tr>`,
    `<tr><td style="font-family:${SANS};font-size:12px;color:${MUTED};mso-line-height-rule:exactly;line-height:19px;padding-bottom:24px;">${esc(view.methodNote)}${esc(held)}</td></tr>`,
    `<tr><td style="border-top:1px solid ${NAVY_RULE};padding-top:20px;font-family:${SANS};font-size:11px;color:${MUTED};mso-line-height-rule:exactly;line-height:18px;">${esc(view.masthead)} &#183; signalnorthintel.com</td></tr>`,
  ];
  return band(rows.join(""), NAVY, "32px 44px 36px 44px", false);
}

function renderShell(view, bands) {
  const preheader = view.theRead ? esc(view.theRead).slice(0, 140) : esc(view.masthead);
  return `<!DOCTYPE html><html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><head>`
    + `<meta charset="utf-8">`
    + `<meta name="viewport" content="width=device-width, initial-scale=1.0">`
    + `<meta name="color-scheme" content="light dark">`
    + `<meta name="supported-color-schemes" content="light dark">`
    + `<style>@media screen and (max-width:600px){.sn-brief-wrap{width:100%!important;}.sn-pad{padding-left:24px!important;padding-right:24px!important;}}</style>`
    + `<!--[if mso]><noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript><![endif]-->`
    + `<title>${esc(view.masthead)}</title></head>`
    + `<body style="margin:0;padding:0;background-color:${PAGE};-webkit-text-size-adjust:100%;text-size-adjust:100%;">`
    + `<span style="display:none;font-size:1px;color:${PAGE};line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">${preheader}</span>`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:${PAGE};"><tr><td align="center" style="padding:32px 12px;">`
    + `<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" class="sn-brief-wrap" style="width:600px;max-width:600px;">${bands}</table>`
    + `</td></tr></table></body></html>`;
}

function renderBrief(view) {
  const bands = [mastheadHtml(view), readHtml(view), leadHtml(view), itemsHtml(view), footerHtml(view)].join("");
  return renderShell(view, bands);
}

function renderBriefText(view) {
  const L = [view.masthead.toUpperCase(), `Week of ${view.weekLabel}`, ""];
  const itemText = (it) => {
    const win = actionWindowText(it.doc.doc_type, it.timing_path, it.doc.published_on, it.doc.date_precision);
    const bits = [it.buyer, formatCad(it.amountCad)].filter(Boolean).join("  |  ");
    const lines = [];
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
    L.push("THIS WEEK", "A quiet week for new signals. We report what the record holds and do not manufacture items to fill space.", "");
  }
  const held = view.reviewedHeldCount > 0
    ? ` ${view.reviewedHeldCount} further item${view.reviewedHeldCount === 1 ? "" : "s"} reviewed this week were held below our materiality bar.`
    : "";
  L.push(view.methodNote + held);
  return L.join("\n");
}

// ---------------------------------------------------------------------------
// Build BriefView from preview JSON
// ---------------------------------------------------------------------------

const METHOD_NOTE =
  "Items are selected on event-date timing (closing soon, or decided in the last "
  + "seven days) and a materiality bar. Every claim links to the publisher's own record.";

function buildViewFromPreview(preview) {
  const items = (preview.items ?? []).map((it) => ({
    headline:     it.headline ?? "(untitled)",
    timing_path:  it.timing_path === "imminent" ? "imminent" : "recent",
    vendorSoWhat: it.vendorSoWhat ?? null,
    buyer:        it.buyer ?? null,
    amountCad:    it.amountCad ?? null,
    doc: {
      doc_type:      it.doc_type ?? null,
      url:           deepLink(it.url ?? null, it.headline ?? null),
      published_on:  it.published_on ?? null,
      date_precision: it.date_precision ?? null,
    },
  }));

  const { lead, supporting } = pickLeadAndSupporting(items);

  return {
    masthead:          "The Weekly Signal",
    weekLabel:         weekLabel(preview.week_start),
    weekStart:         preview.week_start ?? null,
    theRead:           preview.theRead ?? null,
    lead,
    supporting,
    reviewedHeldCount: preview.reviewedHeldCount ?? 0,
    methodNote:        METHOD_NOTE,
    watchlistUrl:      null,
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const key = process.env.RESEND_API_KEY;
  if (!key) { console.error("FATAL: RESEND_API_KEY is not set (ci-preview key required)."); process.exit(2); }

  const to = process.env.BRIEF_PREVIEW_TO || "giancarlodare@gmail.com";
  const from = "The Weekly Signal <signal@signalnorthintel.com>";

  const jsonPath = process.argv[2] ? resolve(process.argv[2]) : resolve("brief_preview.json");
  console.log(`Reading preview JSON: ${jsonPath}`);

  let preview;
  try {
    preview = JSON.parse(readFileSync(jsonPath, "utf8"));
  } catch (e) {
    console.error(`FATAL: cannot read ${jsonPath}: ${e.message}`);
    process.exit(2);
  }

  const view = buildViewFromPreview(preview);
  const html = renderBrief(view);
  const text = renderBriefText(view);

  const subject = `[shadow brief] The Weekly Signal: week of ${view.weekLabel}`;

  console.log(`Sending shadow brief: "${subject}" -> ${to}`);
  console.log(`  ${preview.items?.length ?? 0} items, ${view.supporting.length} supporting, reviewedHeldCount=${view.reviewedHeldCount}`);

  const resp = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify({ from, to: [to], subject, html, text }),
  });

  if (resp.ok) {
    const data = await resp.json().catch(() => ({}));
    console.log(`Shadow brief sent. Resend id: ${data.id ?? "(unknown)"}`);
  } else {
    const body = await resp.text().catch(() => "");
    console.error(`FAILED: HTTP ${resp.status} -- ${body.slice(0, 400)}`);
    process.exit(1);
  }
}

main().catch((e) => { console.error("FATAL:", e); process.exit(1); });
