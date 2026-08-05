// Marketing site header (Claude Design handoff, shared across pages).
// Presentation-only; `current` drives the aria-current page state.

// Maple-leaf mark (operator 2026-08-05, replacing the compass arrow). A
// simplified geometric silhouette -- top fan, side waist, lower lobes, short
// stubby stem -- derived to stay legible down to the 20-22px header/footer
// sizes where the realistic leaf's fine serrations would muddy. Single filled
// path; both colour contexts come from the `fill` prop.
const MARK =
  "M48 4 L56 22 L73 16 L70 33 L90 34 L60 50 L70 62 L52 60 L48 84 L44 60 L26 62 L36 50 L6 34 L26 33 L23 16 L40 22 Z";

export function BrandMark({ size, fill }: { size: number; fill: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 96 96" aria-hidden="true">
      <path d={MARK} fill={fill} />
    </svg>
  );
}

export default function SiteHeader({
  current,
}: {
  current?: "about" | "pricing";
}) {
  return (
    <>
      <header className="site-header">
        <div className="site-header__inner">
          <a href="/" className="brand">
            <BrandMark size={22} fill="#ffffff" />
            <span className="brand__text">
              <span className="brand__name">Signal North</span>
              <span className="brand__sub">Procurement Intelligence</span>
            </span>
          </a>
          <span className="site-header__spacer"></span>
          <a
            className="nav-link"
            aria-current={current === "about" ? "page" : undefined}
            href="/about"
          >
            About
          </a>
          <a className="nav-link nav-login" href="/login">
            Log in
          </a>
          <a className="btn btn--primary btn--nav" href="/pricing">
            Join the network
          </a>
        </div>
      </header>
      <div className="header-offset"></div>
    </>
  );
}
