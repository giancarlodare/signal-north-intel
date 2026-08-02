# Reachability diagnostic: the "unreachable from runner" class (2026-08-02)

Question (operator): CITT, SSHRC, CIHR and AG Ontario load in a browser but
died at connection level from the CI runner. Is it the UA, the egress, or
per-host? Discipline in force: an honest UA is fine; a browser UA exists in
this probe for diagnosis only, and a site deliberately refusing bots is a
boundary we report, never evade.

Method: `scripts/reachability_probe.py`, four runs on the CI runner
(30754826633, 30754975408, 30755057576, 30755158091), each testing
DNS -> TCP -> TLS -> HTTP GET under three UAs (SignalNorthIntel/1.0,
python-requests default, browser-like) plus a curl pass, with four control
hosts including nightly-collected CanadaBuys.

## Verdict: it is not the UA, and it is not one cause. Four classes.

**No host anywhere served a browser UA while refusing the honest UA.** The
browser-like UA never changed a single outcome. The one UA-sensitive
behaviour found runs the other way: canadabuys.canada.ca returns 403 to
python-requests' *default* UA (Azure Application Gateway) while serving our
named UA normally — evidence the honest identified UA is the right posture,
not an obstacle. There is no UA fix to make.

### Class 1 — Per-runner IP lottery (the systemic finding)

gc.ca/on.ca edges block SOME cloud IP ranges; GitHub runners draw from a
huge Azure pool, so reachability is decided per run at TCP, before any
header is sent. Watch the same hosts flip across the four runs, same code:

| host | run 1 | run 2 | run 3 | run 4 |
|---|---|---|---|---|
| www.citt-tcce.gc.ca | OK | OK | TCP-blocked | OK |
| www.sshrc-crsh.gc.ca | OK | OK | TCP-blocked | OK |
| www.auditor.on.ca | TCP-blocked | TCP-blocked | **OK** | TCP-blocked |
| www.oag-bvg.gc.ca (control) | OK | OK | TCP-blocked | OK |

Run 3's control failure made the probe flag its own verdicts as
untrustworthy — the interpretation logic working as designed. Consequence
for the whole pipeline: **a single connection failure from one runner means
nothing.** The coverage probe must never mark a row absent from one
ConnectionError; collectors already retry nightly, which is why this class
never hurt collection, only measurement.

Members: CITT, SSHRC, AG Ontario, AG Canada, and likely South Simcoe
Police, Greater Sudbury, ontariofirefighters.org (reset mid-handshake).
UCCM (www and apex) failed TCP in all four runs — stable cloud-range block
until proven otherwise; browser-live per operator.

### Class 2 — Genuine host changes (not blocks, roster fixes)

* SSHRC: real migration to **sshrc-crsh.canada.ca** (canada.ca
  consolidation; old host 302s; new host verified reachable). Other gc.ca
  rows should be checked for the same consolidation.
* Esprit de Corps: **www.espritdecorps.ca** works; the apex is missing
  from the cert SANs. Our host-variant bug.
* Cochrane DSSAB: redirects to **cdsb.care**.
* mlps.ca, www.countyofrenfrew.on.ca (operator-corrected hosts): verified
  reachable — false negatives closed.

### Class 3 — Dead or wrong domains (NXDOMAIN, egress-independent)

www.saultpolice.com, www.smithsfallspolice.ca, www.porthopepolice.ca,
www.saugeenshorespoliceservice.ca do not resolve at all. DNS is global, so
these are wrong or dead domains, not blocks. Correct domains come from the
OACP websites PDF in the roster-ingest pass.

### Class 4 — Server-side TLS defects (browsers tolerate, strict clients refuse)

* CIHR — all three hosts including **webapps.cihr-irsc.gc.ca** (the
  Funding Decisions Database) serve an incomplete certificate chain
  ("unable to get local issuer certificate"; curl agrees). Browsers do AIA
  chasing; python and curl do not. Legitimate fix: complete the missing
  intermediate in our trust bundle — completing a broken chain is not
  evading anything. Never verify=False.
* www.muskoka.on.ca — DH_KEY_TOO_SMALL: legacy weak Diffie-Hellman.
  Client-side accommodation would mean lowering our TLS security level; a
  decision to surface, not silently take.
* www.scpolice.ca — TLSV1_ALERT_INTERNAL_ERROR from an AWS edge; both
  clients. Needs a second look; possibly also per-IP.

## What this changes

1. **Worklist items 14-29:** mostly false negatives, as suspected — but by
   flakiness and host-drift, not a UA block. Nothing needs or gets a UA
   change.
2. **Coverage report re-read:** of the 17 unreachable rows, 6 are verified
   reachable today, 4 are dead domains (class 3), 4 are TLS defects
   (class 4), 3 remain cloud-blocked-or-flapping (UCCM stable; South
   Simcoe, Greater Sudbury retry class).
3. **Probe hardening (queued):** coverage_probe adopts the layer
   classification, retries connection failures once, and only reports
   "unreachable" with the failing layer named; absent-by-unreachable rows
   require two consecutive runs before they count.
4. **Boundary bookkeeping:** none of this class is a robots refusal. The
   only robots-DISALLOW in the roster remains sarniapolice.com; OTP remains
   the standing robots boundary; FUS grading (login) and CanLII (terms) are
   terms boundaries. Hosts stably blocking cloud ranges while serving
   browsers (UCCM today) are reported as "cloud-egress blocked, live in
   browser" — a distinct category from a bot refusal, and any alternative
   egress is an operator decision, not something collection quietly does.

## Corpus checks that rode along (run 30754829483)

* **Sarnia transition arc:** precursors are IN the corpus — Jan 30 2026
  "everything's on the table" on the new police facility, Feb 11 mayor
  holding the 2026 budget despite a legal notice, Feb 20 mayor asking the
  province to reconsider police budget rules (62 Sarnia matches total).
  The August council motion itself is not yet in the corpus.
* **West Grey headquarters (completing early 2026):** absent — 5 matches,
  none about the HQ. Expected: West Grey only got a roster domain today.
* "OPP costing": 0 matches — the transition-review class starts from zero.
