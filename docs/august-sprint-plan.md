# August sprint plan (Jul 21 to Aug 17)

Operator directive 2026-07-21: complete niche coverage (Ontario + federal,
critical infrastructure / defence / public safety) AND the staged portal by
mid-August. Standing disciplines unchanged: probe-first, validation bars
before enablement, loud failure, provenance, propose-then-approve on new
sources. **We compress the calendar, never the checks.**

**Park rule:** anything stuck 3+ days gets a park-with-verdict and a dated
proxy-coverage line. The sprint never stalls on one stubborn source.

**Reporting:** daily check-in (cleared / in flight / stuck with day count /
parks), delivered every morning for the sprint's duration.

## Week 1 (Jul 21-27): open every front's probe

| # | Front | Method | Deliverable and date |
|---|---|---|---|
| 1 | Provincial layer | data.ontario.ca CKAN search for OTP/tender datasets (IN FLIGHT Jul 21; first run hit a transient 502 on robots, rerun queued with retry) + IO deep crawl: sitemap plus project and vendor-resources pages, grepping for the MERX link both earlier checks missed | Verdict on both by **Jul 23** |
| 2 | Toronto (Ariba) | Public-surface probe before assuming hard: toronto.ca procurement pages (WAF risk noted, operator browser as fallback) + SAP Ariba no-login discovery paths + robots posture | Verdict by **Jul 24** |
| 3 | Ontario Hansard | Probe ola.org document structure (Hansard transcripts, committee estimates), then a requests-based collector design: intent extraction over committee estimates and SolGen / infrastructure statements | Design doc PR by **Jul 25** |
| 4 | bids&tenders saturation prep | Full-Ontario tenant enumeration (directory discovery plus systematic subdomain checks) then batched provenance crawls of each municipality's official site | Enablement-ready table by **Jul 26** |
| 5 | MERX + municipal open data | Buyer-directory sweep beyond the tier-2 slugs (first sweep IN FLIGHT Jul 21) + systematic {city} open-data endpoint probe on the Windsor pattern | Table by **Jul 26** |
| 6 | Render-capable evaluation | Candidates: Playwright-in-CI (incumbent for bids&tenders), Firecrawl, self-hosted alternatives. Criteria: fidelity against eScribe (Hamilton, Niagara, London, Ottawa boards) and Biddingo (DRPS, Windsor backstop), cost, CI fit, robots posture, maintenance load | Recommendation by **Jul 27** |
| 7 | Wave 3 portal design | Marketing site, auth, dashboard + tags, functional watchlist with event logging, Stripe in test mode. STAGED-DARK: nothing public | Design doc PR by **Jul 27** |
| 8 | Sunday gate | The Jul 26-27 brief drafts from the new corpus (Windsor, MERX-Ottawa, five boards) and is the enablement gate for the current cohort | Tier-2 + confirmed MERX buyers enable **Mon Jul 28** on pass |

## Weeks 2-3 (Jul 28 to Aug 10): enable in validated waves

- **Jul 28:** tier-2 bids&tenders cities + confirmed MERX buyers enable
  (post-gate), each through the standard validation dry-run.
- **Jul 28 to Aug 1:** bids&tenders saturation batch 1 (validated wave);
  Hansard collector build + validation, live by **Aug 1**.
- **Aug 1-8:** render adapter build per the Jul 27 recommendation; eScribe
  boards unpark (Hamilton, Niagara, London, Ottawa) and Biddingo DRPS
  un-parks, each against the board-minutes validation bars; Toronto
  proceeds per its probe verdict.
- **Aug 4-10:** saturation batches 2-3; portal build to staged (auth,
  dashboard, watchlist + event logging, Stripe test).
- **Checkpoint (Aug 4):** extraction-budget review; saturation multiplies
  Opus extraction volume, so the projected monthly number is re-stated
  before batch 2 enables.

## Week 4 (Aug 11-17): close

- **Aug 11-13:** final enables; every niche source either live or carrying
  a dated park-with-verdict and proxy-coverage line.
- **Aug 13-15:** portal staged end-to-end (marketing page dark, auth,
  dashboard, watchlist firing on live events, Stripe test checkout).
- **Aug 15-17:** one consolidated coverage map, founding-member-ready;
  Sunday brief drafting from the full corpus.

## Standing risks, named now

- **WAF walls** (ottawa.ca 403, toronto.ca likely): operator-browser
  provenance is the sanctioned fallback, recorded per source.
- **Robots walls** (Jaggaer /esop): honored absolutely; such sources park
  as human-research-only with proxy lines, never scraped around.
- **Render costs**: the evaluation prices them before any adapter builds.
- **Extraction budget**: reviewed Aug 4 before saturation batch 2.
- **Sunday gate failure**: if the brief drafts wrong, tier-2 enablement
  holds until the defect is fixed; the sprint reorders, it does not skip
  the gate.
