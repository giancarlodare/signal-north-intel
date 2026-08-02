// The Weekly Signal reading view (Claude Design handoff: dashboard/brief.html),
// fully wired to the stage-2 member data layer. RLS is the gate; the data
// layer's explicit filters keep the operator preview faithful.
//
// Honest mappings (see the incorporation gap list):
//  - Hero issue line: "The Weekly Signal · Week of <date>" from week_start.
//    The handoff's issue number ("No. 31") has no backing field; omitted.
//  - Hero headline: the lead item's headline (the lead IS the week's story).
//  - The handoff's long body paragraph per item has no backing field; each
//    item renders its title, the editor's vendor note, and its provenance.
//  - Dates render via the standing date-type-label rule (never a bare date,
//    never a fabricated day; month precision renders "Apr 2026").
//  - Save buttons are stage 3b: rendered disabled, no fake persistence.
import { createClient } from "@/lib/supabase/server";
import {
  listPublishedBriefs,
  getBriefItems,
  type PortalItem,
} from "@/lib/portal/data";
import { actionWindow } from "@/lib/brief/date-label";
import { provenanceKind, provenanceLabel } from "@/lib/portal/provenance";
import { listSaved, savedIds } from "@/lib/portal/watch-data";
import { saveItem, unsaveItem } from "../actions";
import RequirePaid from "@/components/portal/RequirePaid";

export const dynamic = "force-dynamic";
export const metadata = {
  title: "The Weekly Signal — Signal North Member",
  robots: { index: false, follow: false, nocache: true },
};

function weekLabel(weekStart: string): string {
  const [y, m, d] = weekStart.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return weekStart;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Toronto",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(Date.UTC(y, m - 1, d, 12)));
}

function SaveButton({
  id,
  enabled,
  saved,
}: {
  id: string;
  enabled: boolean;
  saved: boolean;
}) {
  // Live once the stage-3 DDL is pasted (saved_items readable); disabled
  // pre-paste, never localStorage-fake.
  if (!enabled) {
    return (
      <button
        className="save-btn"
        data-item-id={id}
        disabled
        title="Saving arrives with the next portal stage"
      >
        Save
      </button>
    );
  }
  return (
    <form action={saved ? unsaveItem : saveItem}>
      <input type="hidden" name="brief_item_id" value={id} />
      <button
        className={`save-btn${saved ? " is-saved" : ""}`}
        data-item-id={id}
        type="submit"
      >
        {saved ? "Saved ✓" : "Save"}
      </button>
    </form>
  );
}

function ItemMeta({ item }: { item: PortalItem }) {
  const window_ = actionWindow(
    item.docType,
    item.timingPath,
    item.eventDate,
    item.datePrecision,
  );
  // Honest provenance (operator rule 2026-07-28): the label matches where the
  // click actually lands — record page, publisher listing (text-fragment
  // anchor), or portal landing — and the publisher's reference number renders
  // beside the link so a portal-level record is locatable in two clicks.
  const kind = item.sourceUrl ? provenanceKind(item.sourceUrl) : null;
  return (
    <div
      className="flag-card__meta"
      style={{ borderTop: 0, paddingTop: 0 }}
    >
      {item.buyer ? <span className="mono-meta">{item.buyer}</span> : null}
      {window_ ? <span className="mono-meta">{window_}</span> : null}
      {item.referenceNumber ? (
        <span className="mono-meta" data-field="reference">
          Ref {item.referenceNumber}
        </span>
      ) : null}
      {item.sourceUrl && kind ? (
        <a
          href={item.sourceUrl}
          className="src-link"
          target="_blank"
          rel="noreferrer"
        >
          {provenanceLabel(kind)}
        </a>
      ) : null}
    </div>
  );
}

export default async function BriefPage({
  searchParams,
}: {
  searchParams: { brief?: string };
}) {
  // Paywall. The account page deliberately does NOT use this.
  await RequirePaid();
  const supabase = createClient();
  // Session diagnostic (2026-07-27): names whether this server render holds
  // the member JWT or fell back to anon, which RLS answers with clean zero
  // rows. Shows in Vercel function logs as [portal-data] render session.
  const {
    data: { user: renderUser },
  } = await supabase.auth.getUser();
  console.error(
    "[portal-data] render session:",
    renderUser ? `${renderUser.email} (${renderUser.id.slice(0, 8)})` : "ANON",
  );
  const briefs = await listPublishedBriefs(supabase);

  if (briefs.length === 0) {
    return (
      <main className="fade-rise">
        <div
          className="dash-main dash-main--narrow"
          style={{ paddingTop: 64 }}
        >
          <p data-testid="portal-empty">No published briefs yet.</p>
        </div>
      </main>
    );
  }

  // An explicitly selected brief renders exactly (operator preview); the
  // default walks newest-first to the first brief with a member-visible item,
  // so an honest-empty latest week never blanks the member view while a real
  // issue sits behind it (operator decision 2026-07-27).
  const explicit = briefs.find((b) => b.id === searchParams.brief) ?? null;
  let selected = explicit ?? briefs[0];
  let items = await getBriefItems(supabase, selected.id);
  if (!explicit) {
    for (const b of briefs) {
      const its = b.id === selected.id ? items : await getBriefItems(supabase, b.id);
      if (its.length > 0) {
        selected = b;
        items = its;
        break;
      }
    }
  }
  const saved = await listSaved(supabase);
  const savingEnabled = saved !== null;
  const savedSet = savedIds(saved);
  const lead = items[0] ?? null;
  const rest = items.slice(1);

  return (
    <main className="fade-rise">
      <section className="dash-hero">
        <div
          style={{
            maxWidth: 860,
            margin: "0 auto",
            // 56px bottom pad and the 14px gap are off the named 8px scale;
            // kept to match the handoff target verbatim (flagged for the
            // designer). The other two edges are exact tokens.
            padding: "var(--sp-8) var(--sp-7) 56px",
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          <span className="dash-hero__date" data-field="issue">
            The Weekly Signal · Week of {weekLabel(selected.weekStart)}
          </span>
          {/* .t-title is the design-system display heading (serif, --fs-title,
              1.14, -0.02em); the hero sits on navy so white overrides --ink. */}
          <h1 className="t-title" style={{ color: "#fff" }} data-field="headline">
            {lead?.headline ?? `Week of ${weekLabel(selected.weekStart)}`}
          </h1>
        </div>
      </section>
      <div
        className="dash-main dash-main--narrow"
        style={{ display: "flex", flexDirection: "column", gap: "var(--sp-7)" }}
      >
        {lead ? (
          <article
            style={{ display: "flex", flexDirection: "column", gap: "var(--sp-4)" }}
            data-testid="lead-item"
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: "var(--sp-4)",
              }}
            >
              <span className="flag-card__match">Lead item</span>
              <SaveButton id={lead.itemId} enabled={savingEnabled} saved={savedSet.has(lead.itemId)} />
            </div>
            {/* .t-heading is the design-system panel heading (serif,
                --fs-heading, 1.25, --ink). */}
            <h3 className="t-heading" data-field="title">
              {lead.headline}
            </h3>
            {lead.vendorSoWhat ? (
              <div className="editor-note">
                {/* .t-label with a 10px override to match the handoff (the
                    label token is 11px; flagged for the designer). */}
                <span className="t-label" style={{ fontSize: 10 }}>
                  Editor&apos;s note · G. Da-Ré
                </span>
                <p
                  style={{ margin: 0, fontSize: "var(--fs-ui)", lineHeight: 1.75 }}
                  data-field="editor-note"
                >
                  {lead.vendorSoWhat}
                </p>
              </div>
            ) : null}
            <ItemMeta item={lead} />
          </article>
        ) : null}
        {rest.length ? (
          <hr
            style={{ border: 0, height: 1, background: "var(--line)", margin: 0 }}
          />
        ) : null}
        {rest.map((item) => (
          <article
            key={item.itemId}
            style={{ display: "flex", flexDirection: "column", gap: "var(--sp-3)" }}
            data-testid="brief-item"
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: "var(--sp-4)",
              }}
            >
              {/* Secondary item heading. 25px is OFF the named scale (nearest
                  token --fs-subhead is 24px); kept to match the handoff target
                  verbatim, flagged for the designer to reconcile. */}
              <h3
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: 25,
                  lineHeight: 1.25,
                  letterSpacing: "-0.01em",
                  color: "var(--ink)",
                }}
                data-field="title"
              >
                {item.headline}
              </h3>
              <SaveButton id={item.itemId} enabled={savingEnabled} saved={savedSet.has(item.itemId)} />
            </div>
            {item.vendorSoWhat ? (
              <p
                style={{
                  margin: 0,
                  // 14px is off the named scale (nearest --fs-small 13 /
                  // --fs-ui 15); kept to match the handoff, flagged.
                  fontSize: 14,
                  lineHeight: 1.7,
                  color: "var(--muted)",
                  fontStyle: "italic",
                }}
                data-field="note"
              >
                {item.vendorSoWhat}
              </p>
            ) : null}
            <ItemMeta item={item} />
          </article>
        ))}
        <p data-testid="portal-count" style={{ margin: 0, fontSize: "var(--fs-small)", color: "var(--faint)" }}>
          {items.length} items
        </p>
      </div>
    </main>
  );
}
