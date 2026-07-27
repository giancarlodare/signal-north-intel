"use client";
// Member dashboard header (Claude Design handoff, shared across portal
// pages). Client component only for usePathname (aria-current); identity is
// computed server-side and passed in.
import { usePathname } from "next/navigation";

const MARK = "M48 4 L76 90 L48 72 L20 90 Z";

const NAV = [
  { href: "/portal", label: "Home" },
  { href: "/portal/brief", label: "The Brief" },
  { href: "/portal/saved", label: "Saved" },
  { href: "/portal/watching", label: "Watching" },
] as const;

export default function DashHeader({
  initials,
  shortname,
}: {
  initials: string;
  shortname: string;
}) {
  const path = usePathname();
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
            {NAV.map((n) => (
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
