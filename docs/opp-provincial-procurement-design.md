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

**Probe pass 2 (2026-07-25, CI job 89695342290):**

- Marketplace sitemap: `/sitemap.xml`, `/sitemap_index.xml`, `/sitemap` all
  404. No sitemap to enumerate opportunity listings, so the listings are not
  sitemap-collectable; the marketplace is likely a search-app for
  opportunities. The actual opportunity-listing URL/endpoint is still unknown
  (candidate for an operator browser check or a deeper crawl of the hub links
  below).
- **Real ontario.ca hub found: `ontario.ca/page/doing-business-government-ontario`**
  (200, 101 KB, markers tender/award/procurement). This is the
  publisher-official provenance anchor; its links point to the SCO /
  Vendor-of-Record / marketplace resources. The earlier 404s were wrong slugs.

**Probe pass 3 (2026-07-25, CI job 89698092521):** the hub's real procurement
links point to **Supply Ontario** (`supplyontario.ca`, the provincial
procurement authority, formerly Supply Chain Ontario):

- `supplyontario.ca/become-a-vendor/`: 200, 78 KB, rich procurement markers
  (tender, opportunity, award, closing date, vendor of record, procurement)
  AND **`OPP` is namable in the text** (isolation looks feasible).
- `supplyontario.ca/procurement-bulletins/`: linked as the procurement
  bulletins surface, the likely opportunity/award LISTING feed.
- `doingbusiness.mgs.gov.on.ca/.../psb.nsf/...`: a Lotus Notes .nsf app, 200,
  server-side, procurement marker (legacy buyer info).
- `intra.ontario.ca` VOR page: robots DISALLOWED (OPS intranet); OTP Jaggaer
  `/esop` login: robots-disallowed tree (the standing OTP park).

**Verdict: the collectable provincial surface is Supply Ontario, not the dead
marketplace.** Pass 4 (next): probe `supplyontario.ca/procurement-bulletins/`
(and any feed it links) for the actual opportunity/award listings, robots
posture, server-side vs JS, and whether a buyer/ministry field isolates OPP /
SolGen. If server-side, this is a requests collector on the Windsor/IO pattern;
if a JS app, it joins the render-capable evaluation with a proxy line.

**Probe pass 4 (2026-07-25, CI job 89746865936), FINAL:**
`supplyontario.ca/bulletins/` is 200, server-side (85 KB), procurement markers,
and lists **19 item-shaped bulletins**. But the items are enterprise-wide
Vendor-of-Record ARRANGEMENTS (Employee Assistance, barriers, learning
management, mental-health data sets, boats/motors/trailers, fleet management,
furniture), NOT service-specific opportunities or awards. **OPP is not isolable
here:** the bulletins show province-wide VOR CATEGORIES, not who is buying what.

## OPP OPERATIONAL COVERAGE VERDICT (final, 2026-07-25; stop probing)

Operational OPP procurement is NOT cleanly isolable through public provincial
surfaces, and further probing for a service-level provincial feed is closed
(the feed may not exist publicly):

- Capital / facilities: COVERED via the IO newsroom collector (live).
- Operational: NOT cleanly isolable. The Ontario Tenders Portal (the actual
  solicitation/award system) is robots-walled (/esop Disallow, human-research
  only); Supply Ontario is publicly collectable but only at the province-wide
  VOR CATEGORY level, not service-isolated buys; the legacy .nsf buyer info is
  not an opportunity/award feed.

PROXY-COVERAGE LINE: "OPP capital signal via IO newsroom awards (live);
operational procurement not cleanly isolable through public provincial surfaces
(OTP robots-walled, Supply Ontario category-level only). Federal grants/awards
and ontario.ca news carry residual OPP signal." Revive only if a service-level
provincial award feed becomes public.

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

## Passes 7-8 (2026-07-28): the wall confirmed exactly, and the MERX door found

**Pass 8, the operator's eSOP candidate URLs.** robots.txt on
ontariotenders.app.jaggaer.com, verbatim and in full:

    User-agent: *
    Disallow: /esop

A blanket tree disallow: it covers /esop/toolkit/opportunity/current/list.si
and every variant the operator found. Those pages may well render live
opportunity lists in a human browser, but the publisher's robots policy
disallows automated collection of the whole tree, so under the standing
discipline they are human-research-only. Nothing was fetched. The
ministry/OPP solicitation layer stays closed to collectors unless robots
changes or Supply Ontario grants feed access (a business-development ask,
not a scraping question).

**Pass 7, the public gaps.** The agency layer is NOT walled; it publishes
on MERX:

* oeb.ca/about-oeb/public-tenders (robots-allowed, server-side) lists Open
  and Awarded Opportunities where every item links a public
  merx.com/solicitations detail page, security-relevant items included
  (threat-risk assessment upgrades, access card and detection systems).
* merx.com/metrolinx, merx.com/infrastructureontario, and
  merx.com/cityoftoronto are live public buyer pages, robots-allowed, the
  exact shape the Ottawa collector already parses; merx.com/public/
  solicitations/open is a public cross-buyer list. LCBO and UofT slugs
  404ed (wrong slugs, not walls; correct slugs discoverable).
* Supply Ontario bulletins (/bulletins/, /procurement-bulletins/): a VOR
  ARRANGEMENT catalogue (no dates, no opportunity links); collectable only
  as labeled upstream-intent signal, never as an opportunity feed.

**Standing provincial verdict (supersedes "dead zone"):** ministries and
OPP through OTP stay human-research-only; agencies, crown corps, and
transit are coverable through MERX public buyer pages via the existing
tenders_merx pattern with per-buyer provenance and validation bars. The
MERX-breadth design carries this forward.
