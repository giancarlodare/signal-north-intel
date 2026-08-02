# Coverage re-run on the hardened probe (2026-08-02, run 30756024258)

First coverage report produced under the standing rule: controls checked
first (both reachable — verdicts stand), every fetch retried, every
"unreachable" carrying its failing layer and meaning two consecutive
failures. This table, not the 2026-08-02 morning one, is the basis for any
coverage-page work.

## Headline counts (231 rows probed; 56 sources, 33,678 documents)

| status | rows | note |
|---|---|---|
| covered | 18 | now requires documents actually collected (n_docs > 0) |
| partial | 13 | registered source with 0 docs, or host-only docs |
| absent | 199 | roster grew all day (base hospitals, vendor rosters, news tiers), so absent is larger and more honest than the morning's 171 |
| blocked | 1 | sarniapolice.com, still the only robots-DISALLOW |

The morning report's "28 covered" contained the zero-docs defect; 18 is
the honest number under the corrected rule.

Platform tally: escribe 57 + escribemeetings 4 (= 61), civicweb 5,
granicus 1 — the eScribe-seeding basis for board expansion holds.

## Unreachable rows: 18, every one with a named layer

* **dns x2 (5)** — egress-independent, real host problems:
  saultpolice.com, smithsfallspolice.ca, porthopepolice.ca,
  saugeenshorespoliceservice.ca (dead/wrong domains; real ones come from
  the OACP websites PDF), oacp-b2b.ca (apex may lack an A record — try
  www.oacp-b2b.ca next run). www.ontariocanada.com was our row bug, fixed
  to the apex.
* **tcp-timeout x2 (6)** — the IP-lottery/cloud-block class:
  southsimcoepolice.ca, uccmpolice.com, greatersudbury.ca, auditor.on.ca,
  policearbitration.gov.on.ca (OPAAC — browser-confirmed live by the
  operator today), citt-tcce.gc.ca. CAVEAT the retry cannot remove: both
  attempts share one runner IP, so tcp-timeout x2 on a government host
  still means "this runner's IP range" until a second run from a different
  runner agrees. CITT proves it: reachable twice earlier today, blocked on
  this runner. Cross-run confirmation remains the bar for this class.
* **tls x2 (3)** — server-side defects: scpolice.ca (edge alert),
  muskoka.on.ca (weak DH), webapps.cihr-irsc.gc.ca (incomplete chain; fix
  is completing the intermediate in our trust bundle).
* **reset x2 (3)** — mid-handshake resets, likely bot/cloud filtering at
  hospital and union edges: cper.ca, tbrhsc.net, ontariofirefighters.org.

## Confirmed reachable, notable

iopontario.ca (ALLOW), ero.ontario.ca (ALLOW), fireunderwriters.ca,
sshrc-crsh.canada.ca, espritdecorps.ca (www), cdsb.care, mlps.ca,
countyofrenfrew.on.ca, villagemedia.ca + sootoday.com (ALLOW, rss=True),
open.canada.ca, sedarplus.ca. NSPA and SEC EDGAR serve http403 on
robots.txt specifically — terms/robots need reading by hand before either
is touched.

## What the remaining worklist emission actually is

The probe printed 26 items, but the operator's closures cover most: Hanover
and Deep River domains are in the OACP PDF (roster-ingest pass), non-ON
chiefs associations resolve from cacp.ca/links.html, Pikangikum routes via
NAN/IFNA, Central East has no standalone domain by design. Genuinely open
after today: the 4 dead police domains (OACP PDF), the oacp-b2b www
variant, and the tcp-timeout class pending cross-run confirmation.
