// Marketing site footer (Claude Design handoff, shared across pages).
import { BrandMark } from "./SiteHeader";

export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container site-footer__inner">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 64,
            flexWrap: "wrap",
          }}
        >
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 18,
              maxWidth: 420,
            }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: 11 }}>
              <BrandMark size={20} fill="#ffffff" />
              <span
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: 20,
                  color: "#ffffff",
                }}
              >
                Signal North
              </span>
            </span>
            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.8 }}>
              We report on the market. We never participate in it.
            </p>
            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.8 }}>
              Signal North does not broker, resell, or advise on bids, and takes
              no payment from any party to influence what appears in the record.
            </p>
            <p
              style={{
                margin: 0,
                fontSize: 14,
                lineHeight: 1.8,
                color: "var(--blue-soft)",
                borderTop: "1px solid var(--navy-mid)",
                paddingTop: 16,
              }}
            >
              Advisory services such as grant support, market-entry strategy,
              and program delivery are available through{" "}
              <a href="#">Synapse Advisory</a>, our independent advisory
              practice.
            </p>
          </div>
          <nav
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 10,
              fontSize: 14,
            }}
          >
            <a href="/about">About</a>
            <a href="/pricing">Pricing</a>
            <a href="/contact">Request access</a>
            <a href="/login">Log in</a>
            <span style={{ color: "var(--blue-dim)", paddingTop: 10 }}>
              briefings@signalnorth.ca
              <br />
              Toronto, Ontario
            </span>
          </nav>
        </div>
        <div className="site-footer__legal">
          <span>© 2026 SIGNAL NORTH · TORONTO, ONTARIO</span>
          <span>BUILT ONLY FROM PUBLIC RECORDS</span>
        </div>
      </div>
    </footer>
  );
}
