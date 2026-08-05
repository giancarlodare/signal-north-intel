// Marketing site header (Claude Design handoff, shared across pages).
// Presentation-only; `current` drives the aria-current page state.

// Maple-leaf mark (operator 2026-08-05, replacing the compass arrow). Real
// maple-leaf silhouette from game-icons.net (author Lorc), licensed CC BY 3.0
// -- attribution recorded in docs/decision-log.md. Solid outer silhouette (the
// source's interior vein detail is dropped so it stays clean at 20-22px). Both
// colour contexts come from the `fill` prop. viewBox 0 0 512 512 is the source
// icon's canvas.
export const MARK =
  "M175.094 25.593c-37.263 98.702-18.844 171.333 29.812 231.78-55.864-32.94-102.02-39.746-176.562-29.5 36.104 103.52 114.96 147.68 199.53 147.72-11.347 26.98-13.91 56.395-4.374 88.938 36.643-23.08 58.91-47.936 68.906-78.468 35.98 50.032 94.496 84.814 134.625 96.844l14.595 4.687-2.344-15.187c-2.565-14.66-.2-24.85 5.845-35.063 6.046-10.21 15.88-20.01 28.03-30.937l21.032-18.688-28.03 2.344c-36.735 3.018-73.025-3.842-108.813-33.906 24.9-.342 49.864-6.29 84.843-16.157-18.744-22.37-40.422-35.795-64.468-42.594 51.884-67.147 81.588-166.79 52.936-233.063-82.263 37.32-123.16 89.803-138.75 152.406C280.17 141.16 244.118 77.825 175.094 25.592z";

export const MARK_VIEWBOX = "0 0 512 512";

export function BrandMark({ size, fill }: { size: number; fill: string }) {
  return (
    <svg width={size} height={size} viewBox={MARK_VIEWBOX} aria-hidden="true">
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
