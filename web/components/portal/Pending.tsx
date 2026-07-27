// Honest placeholder for portal features whose backend stage has not landed
// yet (watchlists, saved items, the event log). Uses the handoff's dashed
// empty-state pattern (dashboard/saved.html). These blocks light up as their
// stages land; nothing here pretends to work.
export default function Pending({
  title,
  note,
  testid,
}: {
  title: string;
  note: string;
  testid?: string;
}) {
  return (
    <div
      data-placeholder="true"
      data-testid={testid}
      style={{
        border: "1px dashed var(--line)",
        padding: 48,
        textAlign: "center",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: 22,
          color: "var(--muted)",
        }}
      >
        {title}
      </span>
      <span style={{ fontSize: 14, color: "var(--faint)" }}>{note}</span>
    </div>
  );
}
