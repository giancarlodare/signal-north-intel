# Upstream intent layer: design (validation-first)

Status: PROPOSED (design-first, 2026-07-25). Front 2 of the mid-August scope.
Build now, but VALIDATION-FIRST: this is a signal-vs-noise quality problem,
not a fetch problem. The design is proven on ONE service before it scales;
the one-service precision proof is the accelerator, not a delay.

## 1. What it is

Today the spine catches demand once it surfaces as a solicitation or award.
The upstream intent layer catches it EARLIER: the chatter/intent/commitment
that precedes a solicitation, from the sources where a police service telegraphs
future buying before it hits a procurement portal. It slots into the existing
demand-strength taxonomy (chatter, intent, commitment, in_market, awarded);
this layer populates the first three, which the award spine cannot.

## 2. Sources (per service)

- **Service newsroom / media releases**: the service's own announcements
  (new programs, technology pilots, fleet, facilities).
- **Police board / commission statements and agendas**: budget asks, capital
  plans, staff reports (partly covered by board_minutes where the board is
  collectable; this layer adds the narrative statements around them).
- **Local news** (publisher RSS, on the existing rss_collector pattern):
  council coverage, chief statements, procurement-adjacent reporting.
- **Leading-indicator open data** (demand PRESSURE, upstream of intent):
  crime-rate and incident feeds, notably auto-theft trend data, 911/response
  volumes where published. These do not name a purchase; they raise the prior
  that a service will buy in a category (auto-theft spike precedes ALPR /
  bait-car / investigative-tech buys). Captured as a distinct `pressure_signal`
  input to the demand-arc engine (Front 3), not graded as procurement intent
  directly.

## 3. The quality problem (why validation-first)

Most of this text is press-release noise: awards ceremonies, community events,
hiring, opinion. The value is the small fraction that carries genuine
procurement/funding intent. Scaling a noisy extractor floods the brief with
garbage and destroys trust. So the extractor is proven on one service before
it scales.

Extraction: the existing signal_extractor, given an intent-tuned instruction,
classifies each upstream document as one of {procurement_intent,
funding_intent, pressure_signal, noise} with a demand-strength grade
(chatter/intent/commitment) and a confidence. `noise` is dropped (this is a
scope filter, like Hansard, not keep-all: upstream sources are mostly noise by
volume and keeping it all would swamp the corpus). Opus, per the standing
model rationale.

## 4. The one-service proof (the deliverable that gates scaling)

Pick ONE service with a rich public footprint AND a downstream spine to sanity
against. Recommendation: **Peel Regional Police** (existing board_minutes +
Peel tenders + Method-B awarded collectors give a downstream spine to check
intent against), with **Toronto Police Service** as the fast-follow (highest
news volume; Toronto award history now in the corpus).

Proof procedure:
1. Collect a bounded sample of that service's upstream docs (newsroom + board
   statements + local news + the leading-indicator feeds).
2. Run the intent extractor over them.
3. **Hand-score precision on a labeled sample**: of the docs the extractor
   graded as procurement_intent/funding_intent, what fraction are genuinely
   that (not noise)? Report precision AND recall against a human-labeled set,
   with the confusion cases quoted.

**Gate:** precision on graded-intent >= 0.8 on the sample (tunable with the
operator) before scaling to all services. Below the bar: fix the instruction /
add negative markers / raise the confidence floor, re-measure, do NOT scale.
Above the bar: scale aggressively to all services on the same extractor.

The proof is brought to the operator FAST as a precision table with the
misclassified examples, so the scale/fix decision is made on evidence.

## 4a. Peel source probe (2026-07-25, CI job 89695342290)

- `peelpolice.ca`: server-side (102 KB, ~64k text), news/chief/press +
  crime/api markers. Collectable. The newsroom SUB-URL is not the guessed
  `.aspx` path (all 404); pass-2 crawls the homepage for the actual news link.
- `peelpoliceboard.ca`: server-side (47 KB), news/media-release/press markers.
  Collectable; the meetings sub-URL likewise needs the homepage-link crawl.
- `data.peelregion.ca`: **ArcGIS open-data portal, collectable** (dataset /
  open-data / api / arcgis / opendata hints), the leading-indicator (crime /
  auto-theft) feed source. robots declares a **60s Crawl-delay**, honored, so
  it is a low-frequency pull.
- `opendata.peelpolice.ca`: does not resolve (not a real host).

Next: crawl the two service homepages for their real news/statement listing
URLs, then build the adapter against them plus the ArcGIS feed.

## 5. Build order

1. `src/upstream_intent.py`: source adapters (newsroom + board-statement +
   local-news RSS + leading-indicator feeds) for the one proof service, on the
   shared PoliteFetcher, robots honored, loud-fail on empty.
2. Intent instruction + `--doc-types upstream_intent` extraction path (new
   doc_type via enum migration; `pressure_signal` as a signal input, not a
   brief-facing signal).
3. Run the proof, bring the precision table.
4. On pass: parameterize the adapters by service config rows and scale;
   enable in validated waves like the tier-2 cities.

## 6. Discipline

Scope filter (drop noise), not keep-all. Publisher-linked provenance on every
source. No fabricated dates. Precision gate before scale. The leading-indicator
feeds feed Front 3's demand-arc as pressure inputs, closing the loop from
pressure to intent to solicitation to award.
