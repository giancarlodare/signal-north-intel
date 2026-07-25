# OPP operational procurement via the provincial layer: design

Status: PROBE IN FLIGHT (2026-07-25). Front 1 of the mid-August scope
(operator 2026-07-25): OPP operational procurement, no dependency, this week.
Pulled forward alongside the CPO probe. Probe-first, then this design fills
its verdict section; propose-then-approve before any collector builds.

## 1. Why this front

OPP is likely the largest police buyer in the province and is currently dark
to us except via federal grants and ontario.ca news. Two arcs carry OPP
demand signal:

- **Facilities / capital** through Infrastructure Ontario (already proxied by
  the IO newsroom collector; the IO MERX buyer page stays parked pending
  provenance).
- **Operational procurement** through the provincial central-purchasing layer:
  Supply Chain Ontario (SCO), the provincial Vendor of Record (VOR)
  arrangements, and the marketplace at doingbusiness.mgs.gov.on.ca. This
  design targets that operational layer, which the IO leg does not cover.

## 2. Probe (read-only, robots honored)

`scripts/probe_provincial_procurement.py` (CI, runner egress) reports, per
surface, robots posture, server-side HTML vs JS shell, whether
opportunities/awards/VOR content is present in the raw HTML, feed/API hints,
and whether OPP / Solicitor General buys are namable:

- doingbusiness.mgs.gov.on.ca (SCO marketplace)
- ontario.ca Supply Chain Ontario + Vendor of Record pages
- Ontario Tenders Portal (Jaggaer) robots recheck

**Probe pass 1 (2026-07-25, CI job 89692912290), partial verdict:**

- `doingbusiness.mgs.gov.on.ca` (no-www): robots **DISALLOWED**. Use the www
  host, never this one.
- `www.doingbusiness.mgs.gov.on.ca`: robots **ALLOWED**, 200, **server-side
  HTML** (only 5 scripts, ~8.4k text chars), a "procurement" marker, and a
  **sitemap** hint. This is the collectable surface (Windsor/Toronto pattern),
  but the landing page is thin: the opportunity/award LISTINGS are deeper, so a
  sitemap-driven crawl is needed to find them and confirm OPP/SolGen isolation.
- Ontario Tenders Portal (Jaggaer) root: 200 but a 3.7k stub, no procurement
  markers, consistent with the existing OTP park (robots disallows /esop).
- `ontario.ca` supply-chain / VOR / doing-business slugs: all **404** (guessed
  slugs wrong); the real ontario.ca SCO/VOR page URLs need finding.

**Probe pass 2 (next):** crawl `www.doingbusiness.mgs.gov.on.ca/sitemap*` for
the opportunity/award listing pages and confirm (a) they are server-side and
robots-allowed, (b) whether a buyer/ministry field isolates OPP / SolGen; and
find the correct ontario.ca SCO + Vendor-of-Record page URLs. Then this
verdict finalizes and the collector shape below is chosen.

Open questions the verdict still answers: which surfaces publish
opportunities/awards collectably; whether OPP/SolGen buys are isolable; JS-app
vs requests-collectable per surface.

## 3. Collector shape (conditional on the verdict)

Written against the standing patterns so the build is fast once a surface
passes provenance and robots:

- **If a surface serves structured open data** (CKAN/JSON/CSV, like Toronto):
  a requests collector on the Toronto pattern, buyer/ministry field mapped so
  OPP/SolGen rows tag `defence_relevant` and carry the ministry as buyer_name.
  Hard key on the province's own solicitation/VOR reference.
- **If server-side HTML lists opportunities/awards** (like Windsor/IO): a
  requests collector, per-item parse, per-run NEW-item cap, loud-fail on empty.
- **If a surface is a JS shell**: it joins the render-capable evaluation
  (docs/render-evaluation.md), not a requests build; recorded with a
  proxy-coverage line, never scraped around.
- **If robots disallows** (the OTP /esop precedent): human-research-only,
  proxy-coverage line, never bypassed.

## 4. Provenance and tagging

- Provenance is publisher-linked: a surface is enabled only when an official
  ontario.ca / ministry page links it. SCO and the marketplace are
  first-party provincial publishers by definition; the probe confirms the
  link chain and robots.
- Keep-all with `defence_relevant` tagging. Add OPP / "Ontario Provincial
  Police" / SolGen / "Ministry of the Solicitor General" markers so
  police/public-safety buys tag even when the commodity text is generic.
  ORG_SEED already carries "Ministry of the Solicitor General"; add "Ontario
  Provincial Police" (police_service, provincial, ON) on enablement.

## 5. Validation before enablement (tier-1 bars)

CI dry-run per collector, VALIDATION line: reference + date parse >= 90%,
nonzero rows, OPP/SolGen isolation confirmed on a sample. Below the bar:
diagnose and extend before enabling.

## 6. Relationship to the CPO probe

The cooperative-purchasing (CPO) probe (docs/ROADMAP.md) asks which of the
eleven CPOs publish collectably; this front asks the same of the provincial
central-purchasing layer. They run as one probe pass this week (operator
pulled both forward), one design each, enabled independently on their own
provenance + validation.
