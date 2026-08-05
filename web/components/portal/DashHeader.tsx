"use client";
// Member dashboard header (Claude Design handoff, shared across portal
// pages). Client component only for usePathname (aria-current); identity and
// tier are computed server-side and passed in.
//
// NAV IS TIER-FILTERED (ship-gate 2026-08-04): Pro surfaces (Closing soon,
// Watching) render only for a tier that opens them, via the SAME pure matrix
// the server-side RequireTier guard enforces -- so the nav can never advertise
// a page the guard would bounce. Hiding, not disabling: a Weekly member's
// upgrade path is the account page and the pricing table, not a dead link.
import { usePathname } from "next/navigation";
import { navShows } from "@/lib/billing/tier-surfaces";
import type { Tier } from "@/lib/billing/config";

// Maple-leaf mark (operator 2026-08-05, replacing the compass arrow). Kept in
// sync with the same path in components/site/SiteHeader.tsx (BrandMark); both
// render it white-on-navy.
const MARK =
  "M48 4 L56 22 L73 16 L70 33 L90 34 L60 50 L70 62 L52 60 L48 84 L44 60 L26 62 L36 50 L6 34 L26 33 L23 16 L40 22 Z";

const NAV = [
  { href: "/portal", label: "Home" },
  { href: "/portal/brief", label: "The Brief" },
  { href: "/portal/closing-soon", label: "Closing soon" },
  { href: "/portal/saved", label: "Saved" },
  { href: "/portal/watching", label: "Watching" },
] as const;

export default function DashHeader({
  initials,
  shortname,
  tier = null,
}: {
  initials: string;
  shortname: string;
  tier?: Tier | null;
}) {
  const path = usePathname();
  const items = NAV.filter((n) => navShows(tier, n.href));
  const current = (href: string) =>
    path === href ? ("page" as const) : undefined;
  return (
    <>
      <header className="dash-header">
        <div className="dash-header__inner">
          <a href="/portal" className="brand">
            <svg width="22" height="22" viewBox="0 0 96 96" aria-hidden="true">
              <path d={MARK} fill="#ffffff" />
            </svg>
            <span className="brand__text">
              <span className="brand__name">Signal North</span>
              <span className="brand__sub">Member</span>
            </span>
          </a>
          <span className="dash-header__spacer"></span>
          <nav className="dash-nav">
            {items.map((n) => (
              <a key={n.href} href={n.href} aria-current={current(n.href)}>
                {n.label}
              </a>
            ))}
            <a
              href="/portal/account"
              className="avatar-link"
              aria-current={current("/portal/account")}
            >
              <span className="avatar" data-field="member-initials">
                {initials}
              </span>
              <span data-field="member-shortname">{shortname}</span>
            </a>
          </nav>
        </div>
      </header>
      <div className="header-offset"></div>
    </>
  );
}
