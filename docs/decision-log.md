# Decision log

The versioned record of what was decided and why. Started 2026-08-01 on the
operator's instruction, because decisions had been living only in chat
history and had begun drifting from what the repo actually does.

**Format.** Newest first. One entry per decision, dated, with the reasoning
compressed to what a future reader needs in order to not re-litigate it.
Entries are appended, never rewritten; a reversal is a new entry that names
the one it supersedes.

**Scope.** Decisions, not activity. A bug fix belongs in the safe-class log
at the bottom; a decision about how bugs get fixed belongs up here.

---

## 2026-08-01 — Autonomy: safe class gets merge authority

**Decided.** Merge on green CI without approval for a defined safe class
(collector/extractor bug fixes with test coverage, workflow and CI config,
dependency bumps, tests, docs, `src/`-only changes with no schema change and
no member-facing surface). The gated class is unchanged: migrations, anything
member-facing, anything that spends money, anything changing a public claim
or price or coverage statement, new sources with robots implications, and
anything crossing the client-facing gate.

**Why.** The bottleneck was wall-clock latency on human approval, not
capability or budget. The live_surface fix sat pushed for eleven hours while
collection died a third night. daily-tenders never ran for seventeen nights
behind a one-line cron guard. Guardrails already existed and were being paid
for twice: once to build, once to gate anyway.

**Conditions.** Full suite green; no new silently-swallowed failure path;
logged here. Unclear means not safe class.

**Supersedes.** The blanket "do not enable anything without an operator go"
as applied to the safe class. It still governs the gated class entirely.

---

## 2026-08-01 — Ceremony matches blast radius

**Decided.** Probe → design doc → approval → build remains mandatory for the
gated class and is not required for safe-class work. Default to the heavier
process when blast radius is unclear.

**Why.** The full ritual on a one-line collector fix costs a night of
collection and buys nothing a green suite did not already buy.

---

## 2026-08-01 — Enterprise is display and capture only, no Stripe object

**Decided.** Enterprise appears on the pricing page at "from $45,000 / yr"
with a Get-a-quote form. No Stripe product, price, checkout, or
`STRIPE_PRICE_ENTERPRISE_*` env var is created in advance. Deals are invoiced
by hand the day they close, or through an ad hoc Price scoped to that one
customer. Portal access is provisioned manually, as for founding members.

**Why.** A product catalogue entry for a tier nobody has bought is an
unfinished path someone can find. Enterprise volume does not justify
self-serve, and hand-invoicing a handful of deals is cheaper than maintaining
a checkout for them.

---

## 2026-08-01 — Founding Member never appears on a public or member surface

**Decided.** Founding is a private offer made in conversation. It appears on
no public page, no FAQ, and no member surface. The tier label and Stripe
config remain so an operator-provisioned founding subscription still renders
correctly; what was removed is the path by which a member could select it.

**Why.** It was live as a checkout button on the account page, visible to any
member without a subscription.

---

## 2026-07-31 — Unscoped drain PAUSED; Toronto excluded on measured evidence

**Decided.** The unscoped drain stays paused and
`unscoped-drain-2026-07` is not re-declared. The remaining ~$118 is held
pending the disjointness test on york / peel / london / durham. Tier-3's
remaining 165 docs finish as a SCOPED batch instead, so their cost is
measurable rather than commingled.

**Why.** Toronto's CKAN corpus is city-wide purchasing: 3 police-related
documents in 9,070 captured (0.03%), and all 478 Toronto Police signals in
the arc census come from tpsb.ca, not from Toronto Open Data. The two corpora
are disjoint, so the Toronto slice buys no police arc material.

---

## 2026-07-30 — Earliness is a claim about the record, not about the future

**Decided.** "Months before the solicitation" is a claim about when the
public record exists and is permitted. "The tender lands in Q1" is a forecast
and is not, until precedent matching pairs precursor to outcome on the same
NEED rather than the same category. Written up as `docs/methodology.md` §7.1.

**Test.** Strike the sentence and ask whether what remains still points at a
document a reader can open. If yes, the claim was about the record.

---

## 2026-07-29 — Statistical demand-arc prediction dropped as a product surface

**Decided.** Signal North no longer builds toward statistical demand-arc
prediction as a member-facing feature or an advertised roadmap item. The
replacement is the sourced demand arc as narrative: a dated, deep-linked
chain of public-record events for one buyer's emerging need, with named
comparable precedents, making no statistical claim. The statistical machinery
(Paule-Mandel, significance gates, prediction ledger, human release gate) is
retained as an INTERNAL instrument and is not deleted.

**Why.** More corpus does not fix it; the honest horizon is years.

**Consequence.** Thin arcs are worse than no arcs: an item whose category
carries fewer than two genuine comparables stays a record item.

---

## 2026-07-29 — Cost envelopes bind, they do not merely measure

**Decided.** `src/envelope_guard.py` runs before any extract-backfill batch.
Three outcomes: PROCEED, SKIP (green, surfaced), UNMEASURABLE (raises, red).
An envelope whose cumulative spend cannot be measured is never certified as
having room; `unscoped-drain-2026-07` is seeded `status='unmeasured'` for
exactly this reason.

**Why.** Per-host token logging measures spend. It does not bind it. The
check is what makes an envelope an envelope.

---

# Safe-class change log

Appended automatically for every change merged under safe-class authority.
Date, what, why, and the run or test evidence.

| Date | Change | Evidence |
|---|---|---|
| 2026-08-01 | Autonomy contract added to CLAUDE.md; this log created | docs only |
| 2026-08-01 | Branch deletion confirmed permanently unavailable (see below) | proxy returns `ERR branch deletion is not allowed` |
| 2026-08-02 | `scripts/sourcing_probe.py` + corpus-report option: read-only fire/EMS/defence expansion probe (corpus reads + robots.txt GETs only) | suite green; probe writes nothing |
| 2026-08-02 | Keep-filter widened (general 100->187, defence 37->62) per operator urgency ruling: drop-at-collection = permanent loss. Contracting-mechanics terms held out (would false-tag defence) | suite green; categorization vocab still gated |
| 2026-08-02 | `scripts/disjointness_probe.py` + corpus-report option (york/peel/london/durham, decides the ~$118) | read-only |
| 2026-08-02 | Phase 2 pooling estimator PARKED by operator verdict 2026-08-02: internal instrument, publishes only if a cell honestly clears; no operator review gates it | proxy line, off operator queue |

---

## 2026-08-01 — Branch deletion is permanently unavailable; stop treating it as a bug

**Finding.** Ref deletion is refused by the Claude Code git proxy, not by
GitHub. Reproduced against a throwaway branch with the raw receive-pack POST:

    HTTP 403
    ERR branch deletion is not allowed

The GitHub App's scopes are correct (read/write on code, pull requests and
workflows, repo in the selected list) and pushes that CREATE refs succeed
through the same endpoint in the same session. Only the zero-sha ref update
that expresses a deletion is rejected, and the response carries an Anthropic
request id rather than a GitHub one.

**Decided.** This is environmental and not fixable from the operator's side.
Branch cleanup is a human task done in the GitHub UI, or avoided entirely by
enabling *Settings -> General -> Automatically delete head branches* so merged
PRs clean themselves up. No further retries.

---

## 2026-08-02 — The web test suite had never run in CI

**Finding.** `.github/workflows/tests.yml` ran `python -m pytest` and nothing
else. Every green check on a portal, billing, or marketing PR was the Python
suite alone. The TypeScript tests were green only because a human ran them
locally and reported so, which is precisely the condition the operator ruled
an outage: a monitor reporting success it has not verified.

**Second bug, hidden by the first.** Four test files imported `"./thing"`
rather than `"./thing.ts"`. Under Node's ESM loader an extensionless relative
specifier does not resolve, so those files failed to LOAD and reported zero
failures. Silent. The four were `portal-routes.test.ts`,
`subscription-state.test.ts`, `inquiry.test.ts` and the new
`signup.test.ts` — that is, the paywall's own tests and the pricing page's
capture rules had never executed once. Local count went from 63 passing to 99
on fixing the imports; 34 tests had been invisible.

**Decided.**
1. `tests.yml` gains a `web` job: `npm ci`, `npm test`, `npm run typecheck`,
   on pinned Node 22 (the loader behaviour is version-dependent).
2. The `test` script's glob is quoted so Node's own recursive `**` applies
   rather than the shell's, which silently flattens to one directory level.
3. `lib/loader.test.ts` fails the suite if any relative import in the suite
   drops its extension, and asserts a floor on files discovered. Verified by
   reintroducing the regression and watching it fail.

**Why it matters beyond the fix.** Both halves are the same defect: work that
reports success without verifying it. A test that cannot load is a swallowed
error wearing a green tick.

---

# Safe-class change log (continued)

| Date | Change | Evidence |
|---|---|---|
| 2026-08-01 | Read-only `corpus-report.yml` workflow + `host_residue.py` (#131) | run 30699792679 green; no `ANTHROPIC_API_KEY` in job env |
| 2026-08-02 | CI runs the web suite; `.ts` extensions restored on 4 test imports; `lib/loader.test.ts` guard added | 99 web tests pass (was 63 running), 470 python pass, `tsc --noEmit` clean |
| 2026-08-02 | `reachability_probe.py` + `corpus_search.py` corpus-report options; coverage roster corrections (disbanded Orangeville/Midland recorded, Gananoque/West Grey/Rescu/OPFFA/IoP/MLPS/Renfrew hosts fixed, ERO row, TRANSITION_REVIEW class, ROSTER_INDEXES); "covered" now requires n_docs > 0 (the OTP defect) | runs 30754826633 / 30754829483 green; diagnostic verdict in chat report of same date |
| 2026-08-02 | Reachability diagnostic delivered: no UA-based blocking exists anywhere; four failure classes (per-runner IP lottery on gc.ca/on.ca edges, genuine host migrations, dead domains, server TLS defects). Probe verdict rule queued: unreachable requires two consecutive runs. Roster: SSHRC->canada.ca, CIHR->webapps FDD, Esprit www, Cochrane->cdsb.care, OPAAC gov.on.ca, base hospitals x8, fire reframed to the 32 career departments, vendor-roster provenance rule | runs 30754826633/30754975408/30755057576/30755158091; docs/reachability-report-2026-08-02.md |
| 2026-08-02 | STANDING RULE (from the reachability diagnostic): a single ConnectionError is not evidence of anything. Any probe concluding absence retries and names the failing layer ("unreachable" = two consecutive failures); any probe whose control fails refuses to report. coverage_probe hardened accordingly (retry + layer naming + control gate); coverage report re-runs on the hardened probe BEFORE any coverage-page copy is built from it | operator ruling, this row; probe changes in PR #144 |
| 2026-08-02 | Data-architecture principles adopted (event-sourcing, immutable snapshots, cohort-only instrumentation, structured editorial log, universal provenance, relevance as (item, context)); tier-strategy engineering constraints (no domain pricing gate, Free locks highest-relevance, Enterprise API = scored records, Weekly filters never watches); coverage table gains scope=claimed/roadmap so 199 absent can never read as "covers nothing"; reachability never leaks into the coverage page; SEC EDGAR = compliant via documented API + declared-contact UA, NSPA terms read by hand first | docs/data-architecture-principles.md; probe scope field this PR |
| 2026-08-02 | Board+council fleet plan of record: one adapter for both body types, discovery-pass-first, batch validation table, per-host isolation, staggered politeness, envelope declared before first seeded run. fleet_discovery probe added; bucket table + intake projection decide the schedule | operator directive; docs/board-fleet-design.md; discovery run to follow |
| 2026-08-02 | London Police Service Board is NOT a gap: pub-london.escribemeetings.com eScribe tenant (adapter first wave) + londonpoliceserviceboard.com WordPress packages (TPSB-shaped config, ready pending validation dry-run). All five named services close before launch. Collision rule: "London Police" domain-scoped (City of London UK board at democracy.cityoflondon.gov.uk) | operator resolution; board_minutes.py LPSB entry |
| 2026-08-02 | Fortnight directive: full scope by Aug 16, nothing cut. Safe class WIDENS to collect-only collectors (no schema, no member surface, no LLM spend = build-and-report; unsure = gated); ONE standing August extraction envelope replaces per-batch approvals (guard enforces batch-by-batch); gated items queue into two daily windows; batch-validation harness extends to every new source. Lens side-by-side spec: floors {3,4} x windows {+30,+35} = four sets + discard decomposition + grant +60/+90 horizon; relevance migration pasted by operator | docs/fortnight-plan-2026-08-03.md; operator message of record |
| 2026-08-02 | ENVELOPE APPROVED: $600 standing for August, guard debits the total, surfaces to queue, unspent stays unspent. Window rulings: imminent +30 -> +35 (scorer peak alignment), grants +45 -> +90 (application-assembly horizon); recent window anchors to last published issue (floor 7 days, no cap, loud when stretched) so cadence slips never skip a day of record. Shell-endpoint work: terms/robots checked first, ambiguity reported not proceeded on; loud-failure shape guard built in from day one. Durham + Waterloo boards migrate to tenant path when adapter exists | operator approvals of record; brief_generator changes this PR, 474 tests green |
| 2026-08-02 | Digest protocol effective now: two digests/day (shipped / decisions / blocked), DECISION vs FYI labelling, BLOCKING pulls forward, answer-from-the-repo-first. Standing $600 envelope pasted and verified by operator (three rows) | CLAUDE.md digest protocol section |
| 2026-08-02 eve | Autonomous queue worked: eScribe/CivicWeb adapter (both shapes, api inert-by-default, loud-failure guard, 8 tests) + shell-endpoint probe (all 15 tenants AMBIGUOUS -> api path stopped pending eScribe terms ruling) + standing-programs census (120 programs, PSC-dominated) + roster ingest (dead-domain corrections found) + fleet-validation harness (Hamilton 10mtg/51doc, Kitchener, Oakville clean; 4/6). PRs #152 merged | evening digest of record |

## eScribe automated-access ruling (operator 2026-08-02)

DECISION: proceed with automated collection of eScribe tenant meeting
records, including the JS-shell runtime API. Operator read the terms:
- The privacy policy governs personal information only.
- The terms of use cover cookies and governing law.
- NEITHER addresses automated access.
- robots.txt permits on the tenant hosts.
- These are statutory public records a board is required to publish.
Silence is not prohibition; proceeding is warranted.

TWO STANDING CONDITIONS (binding):
1. The loud-failure guard on the shell/api path is non-negotiable. An
   undocumented endpoint can change without notice, and silent-zero is the
   failure mode that has already cost a day and four nights. (Built:
   escribe_adapter.LoudZeroMeetings, day one.)
2. If eScribe ever publishes terms that DO address automated access, or a
   tenant's robots.txt changes, we STOP and report it as a boundary rather
   than grandfathering ourselves in. The coverage/shell probes re-check
   robots each run; a terms change is a watch item.

Reasoning recorded here so the call is on the record, not in chat.

## Digest cadence fix (operator 2026-08-02)

The "evening" digest fired at 14:25 EDT. Eastern time was computed
correctly (verified: UTC 18:25 -> 14:25 EDT, and tz-db America/Toronto);
the defect was FIRING ON WORK-COMPLETION and labelling by convention. Fix:
digests fire on a fixed Eastern schedule, morning and evening, not when
work happens to finish. Ad-hoc completion reports are not digests and are
not labelled as a window.

## Marketing site header/button cascade fix (2026-08-02)

Operator comparing the live site against the Claude Design originals: the
header CTA rendered as a stretched, rounded, textless red pill and every
nav link was red, on every public page. Diagnosed two upstream cascade
defects, both fixed scoped under `.sn-site` in `app/(site)/site.css` (no
change to globals.css or the internal review tool):

1. SPECIFICITY. tokens.css `.sn-site a { color: var(--red) }` (0,1,1)
   outranked `.btn--primary` and `.nav-link` (both 0,1,0), so ANCHOR-based
   CTAs were red-on-red (invisible label) and nav links went red, while
   `<button>`-based CTAs were fine. Re-declared the colours under `.sn-site`.
2. LEAK. globals.css (operator tool, imported globally by the root layout)
   resets every button `{ flex:1; min-height:44px; border-radius:10px }`,
   never neutralised for the site -> the stretched rounded pill and the
   detached rounded tab underline. Reset `flex/min-height/border-radius`
   under `.sn-site` (radius 0 per the "rectangular, no radius" button spec).

Also gave the hero's ghost button a light face for the navy ground.
Verified by static render harness (computed styles + screenshots, resting
and hover) and the full site suite (99/99 green). One fix corrects the
header, anchor CTAs, tabs, chips and nav across all five public surfaces.

## Marketing site design corrections, round 2 (2026-08-02)

Verified against the design-handoff HTML (ground truth for structure) + the
operator's design screenshots (authoritative for visual language), rendered
locally through the real Next components with real fonts. Three confirmed
defects fixed in `app/(site)/site.css`, all scoped under `.sn-site`:

1. TAB PANELS SHOWED AT ONCE. The `hidden` attribute on an inactive tab panel
   was defeated by the panel's own `display` (e.g. `.point-grid{display:grid}`)
   outranking the UA `[hidden]{display:none}`. "One market, two sides" rendered
   all 8 points and the tab click did nothing. Fix: `.sn-site [hidden]{display:
   none!important}`. Verified: supplier shows 4, tab swaps to the agency 4.
2. TIER PRICE INK. Handoff CSS left `.tier-price` as body ink; brief +
   screenshots show crimson. Fix: `.sn-site .tier-price{color:var(--red)}`.
3. ABOUT STATS WRAPPED. Handoff shipped six facts one row; the live build
   renders seven, and minmax(170px) wrapped the seventh. Fix: minmax(140px) so
   all fit one row. Verified: 7 in one row; hover reveal (red value + centred
   note) intact.

Checked and found ALREADY CORRECT (no change): About section-head motif,
section-04 (no label), FAQ heading/layout, mission two-column — all match the
handoff. Flagged to operator as content/judgment calls, not changed: 6-vs-7
stats count; the single-capability section 02 (real-data-or-nothing leaves an
empty selector rail); the Canadian-owned callout (in screenshots, absent from
handoff+build); section-01 long-heading ellipsis. Suite 99/99 green.

## Marketing site design corrections, round 3 (2026-08-02)

Rendered each surface locally through the real components with the real fonts
(EB Garamond / IBM Plex, fetched and injected since the sandbox proxy blocks
Google Fonts). Applied three more, verified by screenshot:

1. Home 01 point headings wrapped instead of clipping ("Every contract in your
   category" no longer "...categ..."). site.css: `.point h3` white-space normal.
2. Home 02 single-capability state collapsed the empty selector rail to a
   full-width market-record panel. site.css: `.caps[data-placeholder]`.
3. About mission: added the "Canadian-owned and operated" callout card (dark,
   shadowed) from the operator's design screenshots. about/page.tsx. COPY
   TRANSCRIBED from the screenshot -- operator to verify wording.

Still open for the operator (flagged, not changed): 6-vs-7 About stats count;
the "The market record" heading appearing twice in section 02; pricing button
emphasis (outline/outline/dark/red) vs the current content-model buttons.
Suite 99/99 green; typecheck clean.

## Marketing redesign pass, operator notes 2026-08-03

Rendered locally through the real components + real fonts + fixture data.
Home: hero collapsed to one "Join the network" CTA -> /pricing; headline widened
to three lines and carries "and defence" at 52px; content width bumped
1280->1360; section 01 bottom space tightened; the arc (now 03) genericised off
body-worn cameras to "a core system"; its paragraph shortened + widened; the
Coverage section removed from the homepage (its register belongs in the FAQ, and
the FAQ already carries the coverage question). Header CTA -> "Join the network"
-> /pricing. About: dropped the "1 contract held" stat (single digit reads as a
weakness). Pricing: the inline email box is gone -- FreeBriefForm gained a
`reveal` mode so the Free column shows one button until clicked, keeping the tier
row height-aligned; all four tier CTAs are full-width and align on one baseline;
FAQ rebuilt as two columns (serif heading left, accordion right) per the design.
"and defence" added to the page title and the mission line.

STILL OPEN (operator steer needed): what "the mission section isn't centred"
should look like; what specifically to improve on login + /join; whether the
Durham sewer item was a live relevance-filter leak (separate backend fix) or my
sample data; the exact live stat figures (Supabase-sourced, unverifiable here).
Suite 99/99 green.

## Drain cadence retired + Peel finish folded into standing envelope (operator 2026-08-03)

DECISION (operator): retire the extract-backfill drain-cadence trigger. Its
target was the Toronto award backlog; Toronto is excluded on the disjointness
evidence (three police matches in 9,070 docs; TPS signals 100% from tpsb.ca),
and the unscoped drain is paused indefinitely. Do NOT re-point the trigger at
Peel: the standing $600 August envelope (august-2026-standing) replaced the
reason a permission-asking cron existed. Drains are dispatched as part of the
fortnight plan and the guard debits the total.

GUARDRAIL BEHAVIOUR OF RECORD: tonight's tick refused to dispatch when the
workflow's now-required `envelope` input was absent. Refusing to infer an
envelope, flagging the Toronto/Peel scope mismatch, and spending nothing is
exactly the behaviour the required input exists to produce ("an undeclared
spend is what the guard exists to stop"). Operator affirmed the stop.

PEEL FINISH: peel-portal-2026-08 was $54 declared / $20.19 spent / $33.81 left,
~1,824 docs remaining at ~$34.66 -> the last partial batch would be skipped by
~$1. Per operator, the remainder is folded into august-2026-standing rather
than topping up the per-batch envelope (no reason not to combine: independent
inputs, guard stays binding, standing envelope is built to debit the total).
Dispatched extract-backfill on main {limit:2000, include_hosts:
peelregion.bidsandtenders.ca, envelope:august-2026-standing} to finish the host
(queued 204). Trigger deletion itself is pending operator approval of the
list/delete MCP call.

## Coverage section: removed now, rebuild later (operator 2026-08-03)

Removing the homepage coverage register is right for now: its claims were false
(44 police services, "COMPLETE: Ontario policing" against a measured 18). But
it is one of the strongest sections in the original, and the honest version is a
selling point. Bring it back once the coverage-page copy is approved and rebuilt
from the measured table. Tracked, not dropped.

## Envelope seed rate: fresh envelopes need one at creation (operator 2026-08-03)

DECISION (operator): `august-2026-standing` was created with a NULL seed rate on
the reasoning that each batch measures its own per-doc rate before dispatch.
That holds once an envelope has spend history, but the FIRST batch against a
fresh envelope has nothing to measure from, so the guard priced it as
UNMEASURABLE and refused every dispatch (correctly, no spend). This is what
blocked the Peel finish, not the fold itself. Fixed by seeding
`august-2026-standing` at $0.020200/doc. STANDING RULE: a new envelope is
created WITH a seed rate; never ship one with a null rate expecting the first
batch to self-price. The seed only prices batches until real spend exists; the
moment a batch has its own measured rate, that rate governs.

SEED-RATE CAVEAT: $0.020200/doc is the PEEL PORTAL rate (measured $20.19 / 1000
docs, 0 errors, run 30753674483). Board-minute PDFs run longer -- projected
~$0.03/doc for the board backlog. The seed can therefore materially under-price
a board batch at dispatch. Guard behaviour: use each batch's own measured rate
once one exists, and raise to the operator if the seed under-prices a board
batch at dispatch rather than letting it run under a stale seed.

PEEL FINISH (operator go 2026-08-03): re-dispatch the ~1,824-doc remainder
against `august-2026-standing` (now seeded), NOT a top-up of the per-batch
`peel-portal-2026-08`. Topping up a per-batch envelope by ~$8 to finish one host
is exactly the round-trip the standing envelope exists to remove; the standing
$600 envelope has room and the guard stays binding.

## Drain-cadence trigger: parked, stop retrying (operator 2026-08-03)

The retired extract-backfill drain trigger keeps firing because delete_trigger
returns "requires approval" and that MCP prompt does not surface on the
operator's end -- it cannot be cleared from either side. Operator ruling: PARK
it and stop trying. The ticks are harmless (guard-blocked, zero spend); absorb
them silently, drop the item from the digest, do not raise it again unless
something changes. Two days of attention on cosmetic cleanup is enough.

## Expiring-contract row reinstated, scoped federal (operator 2026-08-03)

REVERSAL (operator): the earlier ruling cut expiring-contract tracking from the
table entirely, based on 0 of 548 MUNICIPAL awards carrying an end date. That
conflated federal with municipal. Federal end dates ARE already collected:
src/contracts_federal.py ingests open.canada.ca proactive disclosure
delivery_date (the contract end/delivery date) into award_text today. So
federal expiring-contracts is a STRUCTURING job on data we already hold, not a
collection problem, and it is a real Pro differentiator.

DECISION: row back in the table as "Expiring contracts (federal)", Pro and
Enterprise (Monitoring group). Honest, buildable, closed-column (describes the
tier as it ships). Widens to "federal, plus municipal where the contract term
is published" only if the municipal measurement supports it; otherwise stays
federal-only and says so.

QUEUED, behind the fortnight work (not built this turn):
1. Municipal contract-term MEASUREMENT (read-only, negligible cost): over the
   548 municipal awards, how many link to a tender document stating a contract
   term, and of those how often the term is extractable as a number of years.
   Settles whether the row ever widens to municipal. Operator go given;
   priority is BEHIND the fortnight, not ahead.
2. Federal end-date STRUCTURING/extraction (delivery_date in award_text -> a
   queryable end_date field) that actually backs the row. On the list, not this
   fortnight; scope not cut yet (operator: unless genuinely small).

ARC ROW: renamed "Arc lookup on any buyer and category" (operator wording). The
distinction against Weekly is ANY, not on-demand: Weekly is one arc a week we
choose; Pro is the arc for whatever the member sells into. Mechanical arc
(dated nodes, deep links, precedent set, no prose), clear of the human-release
rule.

## CASL address blocker + free-path decoupling (operator 2026-08-03)

CASL requires a physical mailing address on commercial electronic messages.
Signal North is NOT incorporated; the holdco will be "Provenance Intelligence"
but nothing is registered until ~September, and "Toronto, Ontario" does not
satisfy the requirement. Never invent an entity name or address.

CONSEQUENCE, scoped as a real blocker:
- The free WELCOME (02) and the weekly intelligence brief (#57) are commercial
  and cannot send until a real registered address exists (post-incorporation).
- Whether the free CONFIRM (01) is commercial or transactional is a counsel
  question. If transactional, capture + confirm can ship in August.
- BUILD DIRECTIVE: the free path is built so capture and confirm go live
  INDEPENDENTLY of the welcome, not as one chain. If counsel clears 01 as
  transactional, ship the front half in August and hold only 02 for the
  address. (Design lands in G.)

EMAIL SET (Claude Design export, integrated): text wordmark lockup (no image;
Outlook blocks remote images), 600px, six emails + plain-text twins. Under
change A there is NO Supabase confirm-signup template; 04/05/06 are Supabase
(magiclink/recovery/email_change), 01/02/03 are our own sends. 03's payment
block dropped (Stripe sends its own receipt). Brand: "public safety" unhyphenated;
the brief is the "intelligence brief".

## CASL address SOLVED — correction (operator 2026-08-03)

Correction to the prior entry: the mailing address is confirmed (Richmond Hill
coworking location). The only remaining step is a ~$60 online Ontario
business-name registration to make "Signal North" a legally identifiable
sender. There is NO dependency on incorporation for the free path. The free
path is gated by the ETHICS GATE like everything else, not by a second address
dependency. Keep the entity name a flagged variable (never invent); keep
building capture + confirm independently of the welcome.

## Weekly brief email: state of record (2026-08-03)

Reconciling "no send path exists" vs "#57 pending": both describe different
halves. web/lib/brief/render.ts is REAL, not a stub -- a complete 600px
table-based email (navy masthead, THE READ band, lead card, buyer-grouped
items with dated provenance-labelled links, a standing-exhibit bar chart, navy
methodology footer), and web/app/brief/[week]/route.ts serves the exact same
HTML so web and email cannot drift. web/app/brief/actions.ts sendBriefEmail
DOES send, via Resend from the verified signalnorthintel.com domain, but
OPERATOR-ONLY (RECIPIENT = BRIEF_RECIPIENT or giancarlo@; "no list, no
capture"). So: render + operator-preview send EXIST; the subscriber/list send
(#57) does NOT. The pricing pass's "no send path" was about the free-signup/
list send, which is accurate for that surface.

GAPS: (1) there is NO Free PARTIAL / locked-items version -- render.ts renders
the full brief only. (2) the brief email is a fixed 600px column and overflows
a 390px phone (no fluid media query), unlike the transactional set.
DIRECTION (operator): the email is the hardest of the three brief surfaces
(portal, email, public sample), so design it first and derive the other two;
build the Free partial to the same system.
