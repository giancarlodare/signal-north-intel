// Saved items (Claude Design handoff: dashboard/saved.html).
// STAGE-3B GAP (flagged, expected): the per-member saved_items table has not
// landed, so this renders the designed shell with the handoff's own honest
// empty state. Saved cards light up when stage 3b lands.
export const dynamic = "force-dynamic";
export const metadata = {
  title: "Saved — Signal North Member",
  robots: { index: false, follow: false, nocache: true },
};

export default function SavedPage() {
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
          data-placeholder="true"
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
            Saving arrives with the next portal stage. Save buttons in the
            brief switch on then.
          </span>
        </div>
      </div>
    </main>
  );
}
