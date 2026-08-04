// The member "Closing soon" live surface (Wave 3, operator D1-D4 2026-07-28).
// Reads the member_live_items projection -- the flat, gate-cleared table whose
// gate lives in src/live_surface.py. Presentation-only: the data layer returns
// exactly the columns this page shows; no operator-internal state exists to
// leak. Staged-dark behind PORTAL_ENABLED like every member surface, and the
// route 404s while the flag is off (middleware gate).
import { createClient } from "@/lib/supabase/server";
import { listLiveItems, shortDate, type LiveItem } from "@/lib/portal/watch-data";
import { dateLabel, formatEventDate } from "@/lib/brief/date-label";
import { provenanceKind, provenanceLabel } from "@/lib/portal/provenance";
import Pending from "@/components/portal/Pending";
import RequireTier from "@/components/portal/RequireTier";

export const dynamic = "force-dynamic";
export const metadata = {
  title: "Closing soon — Signal North Member",
  robots: { index: false, follow: false, nocache: true },
};

function ItemRow({ item }: { item: LiveItem }) {
  // "Tender closes 24 Jul 2026" / "Application deadline Aug 2026" via the
  // standing date-type-label rules; month precision never fabricates a day.
  const when = formatEventDate(item.closingOn, item.datePrecision);
  const label = dateLabel(item.docType, "imminent");
  const kind = item.url ? provenanceKind(item.url) : null;
  return (
    <article className="card flag-card" data-testid="live-item">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          gap: "var(--sp-4)",
          flexWrap: "wrap",
        }}
      >
        <span className="flag-card__match" data-field="deadline">
          {when ? `${label} ${when}` : label}
        </span>
        {item.tags.includes("defence") ? (
          <span className="mono-meta" data-field="defence">
            Defence-relevant
          </span>
        ) : null}
      </div>
      <h3 data-field="title">{item.headline}</h3>
      <div className="flag-card__meta">
        {item.buyer ? (
          <span className="mono-meta" data-field="buyer">
            {item.buyer}
          </span>
        ) : null}
        {item.referenceNumber ? (
          <span className="mono-meta" data-field="reference">
            Ref {item.referenceNumber}
          </span>
        ) : null}
        {item.url && kind ? (
          <a
            href={item.url}
            className="src-link"
            target="_blank"
            rel="noreferrer"
          >
            {provenanceLabel(kind)}
          </a>
        ) : null}
      </div>
    </article>
  );
}

export default async function ClosingSoonPage() {
  // Paywall. The account page deliberately does NOT use this.
  // Pro surface (tier ship-gate 2026-08-04): paid AND pro-or-above.
  await RequireTier("/portal/closing-soon");
  const supabase = createClient();
  const items = await listLiveItems(supabase);
  // Freshness is a claim the page proves, not implies (design §Freshness):
  // the newest refreshed_at across the projection is when the collectors last
  // rebuilt it.
  const refreshedAt =
    items && items.length
      ? items
          .map((i) => i.refreshedAt)
          .filter((x): x is string => !!x)
          .sort()
          .at(-1) ?? null
      : null;

  return (
    <main className="fade-rise" data-testid="closing-soon">
      <section className="dash-hero">
        <div className="dash-hero__inner">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-2)" }}>
            <span className="dash-hero__date">Live opportunities</span>
            <h1 className="dash-hero__title">Closing soon</h1>
          </div>
          {refreshedAt ? (
            <span
              style={{ fontSize: "var(--fs-small)", color: "var(--blue-dim)" }}
              data-field="freshness"
            >
              As of {shortDate(refreshedAt)}
            </span>
          ) : null}
        </div>
      </section>

      <div
        className="dash-main dash-main--narrow"
        style={{ display: "flex", flexDirection: "column", gap: "var(--sp-5)" }}
      >
        {items === null ? (
          <Pending
            title="Live opportunities arrive with the next portal stage."
            note="Public-safety tenders and grants closing soon will stream here between weekly briefs."
            testid="live-pending"
          />
        ) : items.length === 0 ? (
          <Pending
            title="Nothing closing in the current window."
            note="Public-safety opportunities closing in the next 30 days will appear here as they are captured."
            testid="live-empty"
          />
        ) : (
          <>
            {items.map((item) => (
              <ItemRow key={item.id} item={item} />
            ))}
            <p
              data-testid="live-count"
              style={{ margin: 0, fontSize: "var(--fs-small)", color: "var(--faint)" }}
            >
              {items.length} opportunities closing soon
            </p>
          </>
        )}
      </div>
    </main>
  );
}
