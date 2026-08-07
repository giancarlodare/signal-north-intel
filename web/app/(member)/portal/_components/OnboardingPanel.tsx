import { dismissOnboarding } from "../actions";

function nextMondayEastern(): string {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Toronto",
    weekday: "long",
    hour: "numeric",
    hour12: false,
  }).formatToParts(now);
  const weekday = parts.find((p) => p.type === "weekday")?.value ?? "Tuesday";
  const hour = parseInt(parts.find((p) => p.type === "hour")?.value ?? "12", 10);
  const dayNum: Record<string, number> = {
    Sunday: 0, Monday: 1, Tuesday: 2, Wednesday: 3,
    Thursday: 4, Friday: 5, Saturday: 6,
  };
  const d = dayNum[weekday] ?? 0;
  let daysToAdd = (8 - d) % 7 || 7;
  // Monday before 6am Eastern: the brief lands today
  if (d === 1 && hour < 6) daysToAdd = 0;
  const nextMon = new Date(now.getTime() + daysToAdd * 86400e3);
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Toronto",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(nextMon);
}

export default function OnboardingPanel() {
  const nextBriefDate = nextMondayEastern();
  return (
    <div className="onboard-panel" data-testid="onboarding-panel">
      <div
        style={{
          background: "#fff",
          border: "1px solid var(--line)",
          borderTop: "3px solid var(--navy)",
          borderRadius: "var(--radius)",
          padding: "28px 32px 26px",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 16,
            marginBottom: 22,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span className="t-label">Getting started</span>
            <p
              style={{
                margin: 0,
                fontFamily: "var(--font-serif)",
                fontSize: 22,
                lineHeight: 1.25,
                color: "var(--ink)",
              }}
            >
              Your membership is active. Here is what you have.
            </p>
          </div>
          <form action={dismissOnboarding} style={{ flexShrink: 0 }}>
            <button
              type="submit"
              style={{
                background: "none",
                border: "1px solid var(--line)",
                color: "var(--muted)",
                fontFamily: "var(--font-sans)",
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                cursor: "pointer",
                padding: "6px 14px",
                whiteSpace: "nowrap",
              }}
            >
              Dismiss
            </button>
          </form>
        </div>

        <div className="onboard-cells">
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            <span className="t-label">What you have access to</span>
            <p
              style={{
                margin: 0,
                fontSize: "var(--fs-ui)",
                lineHeight: 1.7,
                color: "var(--body)",
              }}
            >
              The complete member edition of the Weekly Signal: full tender and
              award tables, buyer profiles, and the source document linked to
              every line.
            </p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            <span className="t-label">Your first brief</span>
            <p
              style={{
                margin: 0,
                fontFamily: "var(--font-serif)",
                fontSize: 20,
                lineHeight: 1.2,
                color: "var(--ink)",
              }}
            >
              {nextBriefDate}
            </p>
            <span className="mono-meta">Monday, 6:00 am Eastern</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            <span className="t-label">Track what matters</span>
            <p
              style={{
                margin: 0,
                fontSize: "var(--fs-ui)",
                lineHeight: 1.7,
                color: "var(--body)",
              }}
            >
              Add buyers and keywords to get flagged the day a matching
              document appears, before the brief lands.
            </p>
            <a
              href="/portal/watching"
              style={{
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              Set up watchlist &rarr;
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
