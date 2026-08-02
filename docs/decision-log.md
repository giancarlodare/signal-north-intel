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
