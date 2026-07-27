// Saved items (Claude Design handoff: dashboard/saved.html), live against
// stage-3 saved_items (owner-scoped RLS). Pre-paste, the query returns null
// and the page shows the pending note; post-paste, the handoff's own empty
// state covers the zero-saves case honestly.
import { createClient } from "@/lib/supabase/server";
import { listSaved, shortDate } from "@/lib/portal/watch-data";
import { unsaveItem } from "../actions";

export const dynamic = "force-dynamic";
export const metadata = {
  title: "Saved — Signal North Member",
  robots: { index: false, follow: false, nocache: true },
};

export default async function SavedPage() {
  const supabase = createClient();
  const saved = await listSaved(supabase);

  return (
    <main className="fade-rise">
      <div
        className="dash-main dash-main--narrow"
        style={{
          paddingTop: 64,
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        <div className="page-head">
          <h1>Saved</h1>
          <span style={{ fontSize: 15, color: "var(--muted)" }}>
            Items you flagged, as they stood when you saved them.
          </span>
        </div>

        {(saved ?? []).map((item) => (
          <article
            key={item.briefItemId}
            className="card flag-card"
            data-saved-card
            data-testid="saved-item"
            style={{ padding: "24px 28px", gap: 10 }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: 16,
                flexWrap: "wrap",
              }}
            >
              <h3 style={{ fontSize: 22 }} data-field="title">
                {item.headline ?? "(untitled item)"}
              </h3>
              <form action={unsaveItem}>
                <input
                  type="hidden"
                  name="brief_item_id"
                  value={item.briefItemId}
                />
                <button
                  className="save-btn"
                  data-remove-saved={item.briefItemId}
                  type="submit"
                >
                  Remove
                </button>
              </form>
            </div>
            <div
              className="flag-card__meta"
              style={{ borderTop: 0, paddingTop: 0 }}
            >
              {item.buyer ? (
                <span className="mono-meta">{item.buyer}</span>
              ) : null}
              <span className="mono-meta">Saved {shortDate(item.savedAt)}</span>
            </div>
          </article>
        ))}

        {(saved ?? []).length === 0 ? (
          <div
            style={{
              border: "1px dashed var(--line)",
              padding: 48,
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
            data-saved-empty
          >
            <span
              style={{
                fontFamily: "var(--font-serif)",
                fontSize: 22,
                color: "var(--muted)",
              }}
            >
              Nothing saved yet.
            </span>
            <span style={{ fontSize: 14, color: "var(--faint)" }}>
              {saved === null
                ? "Saving arrives with the next portal stage."
                : "Use Save on any item in the brief or your flags."}
            </span>
          </div>
        ) : null}
      </div>
    </main>
  );
}
