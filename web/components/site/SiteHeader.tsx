// Marketing site header (Claude Design handoff, shared across pages).
// Presentation-only; `current` drives the aria-current page state.

const MARK = "M48 4 L76 90 L48 72 L20 90 Z";

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
          <a
            className="nav-link"
            aria-current={current === "pricing" ? "page" : undefined}
            href="/pricing"
          >
            Pricing
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
