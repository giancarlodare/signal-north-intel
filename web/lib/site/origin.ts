// The ONE place the app decides what origin goes into an emailed link.
//
// WHY THIS EXISTS (operator 2026-08-02, the localhost fallback incident).
// The old confirmUrl() derived the origin purely from request headers:
//   Origin -> x-forwarded-host -> host
// That is correct on every legitimate request, but it is UNBOUNDED: it emits
// whatever origin the request claims. Whether the emailed link then honours
// it is decided entirely by Supabase's redirect allow-list, and a mismatch is
// a SILENT fallback to the dashboard Site URL. Two consequences:
//   1. Any new preview pattern or a production domain change reproduces the
//      localhost bug with no error anywhere on our side.
//   2. The header trust is also why the allow-list must stay strict: a
//      spoofed Host header putting an attacker origin into a victim's email
//      is only stopped by Supabase refusing the unlisted redirect. The
//      silent fallback is load-bearing security, not just an annoyance.
//
// THE RULE: in production the origin is PINNED by NEXT_PUBLIC_SITE_URL and
// never derived from headers, so production email links depend on exactly one
// knob (the env var must match the allow-list / Site URL). Previews keep the
// header derivation, covered by the wildcard redirect entry. VERCEL_ENV
// guards the split so a var accidentally scoped to Preview cannot send
// preview testers to production.
import { headers } from "next/headers";

export function siteOrigin(): string {
  const pinned = (process.env.NEXT_PUBLIC_SITE_URL ?? "")
    .trim()
    .replace(/\/+$/, "");
  const env = process.env.VERCEL_ENV; // "production" | "preview" | "development"
  if (pinned && (!env || env === "production")) return pinned;

  const h = headers();
  return (
    h.get("origin") ??
    `https://${h.get("x-forwarded-host") ?? h.get("host") ?? ""}`
  );
}
