// Marketing site header (Claude Design handoff, shared across pages).
// Presentation-only; `current` drives the aria-current page state.

// Maple-leaf mark (operator-approved 2026-08-05). The official Canadian flag
// maple leaf -- the precise 11-point flag geometry (rounded lobe tips), taken
// from a public-domain flag SVG (hampusborgos/country-flags), so there is NO
// attribution obligation. Single solid path; both colour contexts come from the
// `fill` prop. viewBox frames the leaf with even headroom around the top spike
// (a tight crop clipped it -- the top point sits near y~50 in the flag geometry,
// and getBBox mis-reported it).
export const MARK =
  "M4890 4430l-45-863a95 95 0 01111-98l859 151-116-320a65 65 0 0120-73l941-762-212-99a65 65 0 01-34-79l186-572-542 115a65 65 0 01-73-38l-105-247-423 454a65 65 0 01-111-57l204-1052-327 189a65 65 0 01-91-27l-332-652-332 652a65 65 0 01-91 27l-327-189 204 1052a65 65 0 01-111 57l-423-454-105 247a65 65 0 01-73 38l-542-115 186 572a65 65 0 01-34 79l-212 99 941 762a65 65 0 0120 73l-116 320 859-151a95 95 0 01111 98l-45 863z";

export const MARK_VIEWBOX = "2260 -140 5080 5080";

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
