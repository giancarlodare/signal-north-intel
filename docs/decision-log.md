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
