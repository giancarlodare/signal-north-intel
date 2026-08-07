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

## 2026-08-07 — Drain cadence trigger deleted (operator approved)

**Decided.** The extract-backfill drain cadence trigger is deleted. Toronto award
backlog was retired on 2026-08-03 on disjointness evidence (3 police matches in
9,070 Toronto Open Data docs; TPS signals 100% from tpsb.ca). The trigger was
supposed to be deleted at the time; operator approval was pending. Deletion
approved 2026-08-07. No further ticks will fire.

**Mechanical note:** The `list_triggers` / `delete_trigger` MCP calls require UI
permission approval (separate from operator chat approval). Trigger deletion
completes once that permission is granted.

---

## 2026-08-06 — Phase 2: relevance lens + weighted ranking live (safe class, operator approved)

**Decided.** Ship the full lens redesign to `brief_generator.py`:

1. `apply_lens()` now gates on `max_relevance >= 3` (floor ruled from the 200-signal calibration batch: bimodal distribution, floor 3 adds 45 items vs floor 4, the 11 items between them are worth a human eye in shadow cycles). Replaces `materiality >= 4` gate. Defence-relevant always keeps.

2. `rank_key()` replaced with a 6-factor weighted score: category_relevance (0.25, proxy via max_relevance/5), buyer_type (0.15, from org_type), arc_connection (0.30, proxy via cluster member count), actionable_window (0.15, curve peaking 21-35 days), materiality_norm (0.10), grade_norm (0.05). Timing paths are no longer an absolute partition; they feed the actionable_window curve.

3. `relevance` added to the PostgREST SELECT in `run()`. `max_relevance` and `org_type` added to cluster dict.

4. New workflow `relevance-backfill.yml`: dispatch-only, no limit, 90-minute timeout. Ready to fire.

5. `calibration_audit.py` BOUNDARIES updated: the lens no longer uses materiality, so the only materiality decision boundary is the Path A bar (RECENT_MIN_MATERIALITY=3).

**Reasoning.** The calibration batch measured a bimodal distribution and the scorer is doing real work. Both floors are additive — nothing currently passing drops. The actionable_window curve fixes the fundamental problem: soonest-first was actively wrong for subscribers who need time to respond.

**Next.** Dispatch the backfill workflow (approved spend, ~12,000 signals at Haiku-class pricing). Shadow brief cycle follows.

---

## 2026-08-06 — First-visit onboarding panel + Day-2 email (gated, operator approved)

**Decided.** Build and ship:
1. `OnboardingPanel` in the member portal: visible to paid members with account
   age < 48h and no `user_metadata.onboarding_dismissed` flag. Shows access
   summary, next Monday brief date, and watchlist prompt. Dismiss button sets
   `onboarding_dismissed: true` via `dismissOnboarding()` server action.
   No schema migration: dismissal persists in `user_metadata`.
2. `07-member-day2.html/.txt` email template: same visual design as
   `03-member-welcome`. Variables: `{{next_brief_date}}`, `{{portal_url}}`,
   `{{watching_url}}`.
3. `web/scripts/ci/send-day2-emails.mjs`: queries paid members created 24-48h
   ago without `day2_sent` flag, sends via Resend, marks `day2_sent: true`
   in `user_metadata`. Loud failure: any error sets exitCode=1.
4. `.github/workflows/day2-email.yml`: daily cron at 9am ET (dual UTC +
   Eastern hour guard), workflow_dispatch for manual runs.

**Why.** New member experience gap: a member who joins sees an empty portal
with no orientation. The panel removes ambiguity (what do I have, when does it
start) on first login. The Day-2 email catches members who have not returned.

**Gated class.** Member-facing and marketing-site changes per CLAUDE.md.
Operator approved both features on 2026-08-06.

**Not shipped yet.** `03-member-welcome` wiring in the Stripe webhook is still
unwired (no email send on purchase). That is a separate decision.

---

## 2026-08-06 — Da-Ré Advisory firm name corrected

**Decided.** "Da-Ré Advisory" applied exactly: capital D, lowercase a, capital
R, lowercase e with accent (e-acute), capital A in Advisory. Applied to
SiteFooter, about/page.tsx, and all design-handoff prototype HTML files.
The copyright line also corrected to match.

**Why.** The firm name is a legal identity. An incorrect rendering is an error
on a public-facing surface.

---

## 2026-08-06 — Safe-class: relevance scorer + calibration batch (2026-08-06)

**Changed.** `src/relevance_scorer.py` (new): scores `signals.relevance` 1..5
via Haiku-class LLM (title + summary in, integer out, JSON-schema constrained).
`tests/test_relevance_scorer.py` (new): 14 fixture tests covering clamping,
fallback parse paths, dry-run write isolation, error counting, and limit
enforcement. `scripts/relevance_calibration.py` (new): stratified 200-signal
sample, scores via scorer, renders side-by-side lens comparison table (current
vs relevance floor 3 and 4, windows +30 and +35). `.github/workflows/relevance-
calibration.yml` (new): workflow_dispatch, dry-run/run toggle.

**Why.** Scorer is Phase 1 gate before floor ruling and apply_lens update.
No schema change (migration 2026-08-02 already applied), no member-facing
surface, no money spent until calibration workflow is dispatched. Safe class
by CLAUDE.md criteria.

**Also.** Fixed `_USER_TEMPLATE` curly-brace escaping (`{{"relevance": ...}}`):
the literal JSON in the prompt return line was being parsed as a `.format()`
placeholder and raising KeyError at scoring time.

---

## 2026-08-05 — Corridor: collection ON, construction pack + extraction holdback

**Decided (operator directive).** The Corridor vertical's collection turns on
immediately: a `# ---CONSTRUCTION---` keyword pack keeps civil-works documents
the keep-filter was discarding on portals we already visit (permanent loss
daily). Term pack over capture-all: unmatched rows can never be
domain-attributed, and domain-as-a-dimension is now load-bearing.

**Extraction isolation (operator requirement, same day).** Construction-ONLY
keeps insert as `status='captured_construction'`; the daily forward pass and
extract-backfill select exact `status='captured'` (verified sole selectors),
so the daily extraction budget cannot grow. Corridor extraction later targets
the held status under its OWN envelope. No migration (unconstrained status
text; the 'irrelevant' quarantine precedent). Storage delta immaterial on the
forward pass; awarded-history drains would be the material case and remain
envelope-gated.

**Also binding.** (a) The design-award → construction-tender chain per buyer
and asset class stays queryable — the design-side terms are in the pack so
both ends are captured; unit-price extraction is later and envelope-gated.
(b) Construction is the fourth domain DIMENSION (police/fire/EMS/defence/
construction), never a fork. Full scope: docs/corridor-collection.md.

---

## 2026-08-05 — Contract chains stay queryable as chains (capital-reader option)

**Decided (operator addendum, NATO 2026 Summit outputs).** Where a defence
contract's full history is held (award → options exercised → extensions →
value changes), the linkage is preserved as a first-class chain. The current
federal ingest already satisfies this, and the behavior is now BINDING:
`contracts_federal.py` keys re-disclosures on reference + value, so an
amendment inserts as a fresh dated document (original kept, original_value /
amendment_value captured), and grouping on `documents.reference_number` in
disclosure order yields the contract's revenue trajectory. Re-disclosures are
never collapsed into updates; reference_number remains the chain key.

**Why.** The trajectory is the credit signal a future capital-markets reader
would pay for, and it is derivable from what we already collect ONLY if the
linkage survives. Costs nothing today; losing it silently would cost the
option. The full addendum — three NATO/BDC candidate sources (Aggregated
Demand Signal as a revision-tracked document class, Innovation Scale-Up
Package, BDC investment announcements) and the two-reader lens on
ITB/DIP/Estimates/ACAN — is docs/adjacent-collection-design.md §8.
Collect-only, fortnight queue, nothing jumps.

---

## 2026-08-04 — SHIP-GATE: tier gating on portal surfaces before launch

**Built same day (operator go).** `lib/billing/tier-surfaces.ts` is the one
pure surface→tier matrix (closing-soon, watching = Pro+; brief, saved =
Weekly+; founding ≥ pro), read by BOTH the server-side `RequireTier` guard on
the two Pro pages and the tier-filtered member nav, so they cannot disagree.
A Weekly member reaching a Pro surface lands on `/portal/account?access=tier`,
which renders the Pro early-access CAPTURE prefilled with their verified
address — the operator's ruling: that member is the strongest upgrade signal
we have, so it is treated as one, never shown a bare refusal.


**Finding (operator, from the production dark-run).** The portal gates
paid-vs-unpaid only. `grantsPortal()` treats every active tier
(weekly/pro/founding) identically, and the member nav is static — so a Weekly
member reaches Closing-soon and Watching, which the pricing table sells as Pro.
Nothing anywhere enforces tier.

**Ruling.** Ship-gate: the tier table must not claim a distinction the product
does not enforce. Before launch, Pro-tier surfaces (closing-soon board,
watchlists/alerts) are gated by tier, with the Weekly member redirected to an
honest upgrade state, and the nav filtered to what the tier can reach. Build is
gated class (member-facing): a small pure surface→tier matrix + per-page guard +
nav filter, proposed and approved before it lands.

---

## 2026-08-04 — Don't let a branch sit open once its work is done

**Rule.** A branch whose work is finished and green does not wait for a human.
Main moves several merges a day, and every day a branch waits makes the eventual
merge worse. If a change is safe class (per the 2026-08-01 autonomy grant) and
CI is green, merge it — resolve mechanical conflicts by rebasing on current
main; only a substantive conflict (a real disagreement about behaviour, not a
combined option list) goes to the operator.

**Corollary.** Extracting a sub-part to land it early (e.g. lifting the CI
workflow files out of a gated PR into their own safe-class PR) is preferred over
holding the whole thing until the gated part is ready. It also means the gated
branch must be rebased on main afterward so it does not rot.

**Applied.** #138 (salary ledger, collect-only, approved design, migration
already pasted) rebased on main and landed; its only conflict was the
corpus-report option list, purely mechanical. #155 lifted the two dispatch-only
CI workflows out of the gated change-A branch and landed them so they could be
dispatched.

---

## 2026-08-04 — A planning document is not an outcome (editorial discipline)

**Rule.** Never let a planning document read as an outcome. A work-plan item is
not a finding. A tender is not an award. An intent is not a commitment. When a
node is built from a source, the node may assert only what the source's own
text asserts, at the source's own stage in the process.

**Origin.** The TPS 9-1-1 / priority-response node. The corpus text is the City
of Toronto Auditor General's 2023 WORK PLAN scheduling two reviews of the
Service (911 PSAP operations; responses to calls for service). It was nearly cut
as unusable because it read as an audit FINDING against a named service, which
the document does not contain. Pulling the source sentence showed the node is
usable, but as *scheduled scrutiny*, not a finding. Wording that survives:
"In February 2023 the City of Toronto Auditor General's work plan scheduled two
reviews of the Service, covering 9-1-1 public safety answering point operations
and responses to calls for service." Source: TPSB minutes 2023-11-23.

**Why it recurs.** The rung taxonomy already encodes this (precursor rungs 2-3
vs outcome rungs 4-5), but composed prose can quietly promote a rung: a
scheduled review narrated as a finding, a posting narrated as an award. The
verification that catches it is reading the source sentence, not the summary.

---

## 2026-08-04 — The /portal dashboard is Pro monitoring material, not superseded

**Decided.** The stage-2 "N things changed" dashboard that used to sit at
/portal is NOT deleted and was not superseded by change A. It is a MONITORING
surface, and monitoring is Pro. It is logged here as Pro material alongside the
closing-soon board, watchlists and alerts. Weekly members land on the brief,
because the brief is what they bought, so /portal stays a pure redirect (paid →
/portal/brief, unpaid → /portal/account).

**Why.** Change A's redirect made the dashboard look discarded; the operator's
correction is that it was misplaced, not obsolete. Putting a monitoring view in
front of a Weekly member shows them a Pro capability they have not bought; the
brief is the Weekly product and the right landing.

**Corrects.** The "judgment call flagged for reversal" note in the change-A
entry below, which framed the dashboard as superseded. It is reclassified, not
removed.

---

## 2026-08-04 — Email preview send uses a scoped, disposable key, never production

**Decided.** The dispatch-only workflow that sends 02/03 to a real inbox
(.github/workflows/email-preview-send.yml + web/scripts/send-preview-emails.mjs)
runs against a SEPARATE Resend key: a sending-only key named ci-preview, added
as the Actions secret RESEND_API_KEY, revoked once the two emails have been
reviewed. The production key is never placed in GitHub Actions.

**Why.** Real-client rendering differs enough from a browser preview to be worth
doing, and these are the first thing a customer sees from us. But a leaked
sending key on our own verified domain is a phishing and reputation risk, so it
gets a scoped, short-lived key rather than the real one. The four Supabase
templates are not sent here at all: their faithful render is Supabase's own
send, done in the install session, never faked from a script.

---

## 2026-08-04 — Change A: checkout-first paid flow (email-anchored provisioning)

**Decided.** "Join Weekly" goes straight to Stripe Checkout with NO account and
no login. Checkout collects the email/name/card; the webhook provisions the
account from the Stripe-verified email and emails a sign-in link. This REVERSES
the confirm-before-pay flow (2026-08-02), where an account was created and
verified before checkout.

**How identity resolves now.** The webhook was "matching NEVER uses email"
(2026-08-01). It is now stamp-first, then email. (1) An `sn_member_id` stamp on
the subscription/session/customer still wins — that is the signed-in path (a
member subscribing from /portal/account) and dashboard actions, unchanged. (2)
On `checkout.session.completed` only, with no stamp, the Stripe-verified email
is the anchor: `admin.generateLink(magiclink)` finds the account or creates one,
and the id is stamped back onto the subscription + customer so every later event
resolves by stamp. Provisioning happens on `completed` only; bare
`subscription.*` events resolve by stamp and 500-retry until `completed` has
stamped, avoiding double-provision and email/stamp races.

**Free-list dedup.** On provision, `brief_signups.unsubscribed_at` is set for
the anchor email, so a Free upgrader is on the paid list only, never both.

**Reconciliation alarm (the one out-of-window interrupt).** A PAID checkout that
cannot be provisioned (no email, unmapped price, failed admin call) is recorded
in the new `provisioning_failures` table and the operator is emailed directly
with an unmistakable subject (`[SIGNAL NORTH — ACTION] Paid, not provisioned:
<email>`). The table makes the alarm fire ONCE per stranded subscription, not
once per Stripe retry, and is the operator's open worklist. Manual fix:
`node web/scripts/provision-member.mjs <sub_id|email>` (idempotent). The alarm
is internal ops and is NOT gated by the member-email flag; it needs only
`RESEND_API_KEY`.

**Member sends are armed by a flag.** `MEMBER_WELCOME_LIVE` (default off, same
shape as `PORTAL_ENABLED`) honours "don't wire any send path until I've approved
the rendered result." While off, a purchase still provisions + entitles and logs
the sign-in link, but no welcome is sent. Flip it on AFTER the rendered emails
are approved, before the first live sale. The welcome (template 03) is embedded
byte-identical to `web/emails/03-member-welcome.{html,txt}`, guarded by a test,
so the thing sent is the thing approved.

**/portal is now a redirect, regardless of PORTAL_ENABLED.** It sends paid →
/portal/brief, unpaid → /portal/account, and never 404s (fixing the magic-link
landing bug). The gate also changed: a SIGNED-IN member reaches the member
surface regardless of the flag, so a purchase works before the marketing-site
flip. The public is still bounced to /login while dark; the paywall still
governs every product page. **Flag flip stays a deliberate, separate operator
decision, never coupled to a purchase.**

**Judgment call flagged for reversal.** Making /portal a pure redirect
supersedes the stage-2 member dashboard that lived at the index. The dashboard
JSX is preserved in git history; if the operator wants it back as a route, say
so. Chosen because the operator's ruling was explicit ("/portal becomes a
redirect ... /portal/brief (paid) or /portal/account (unpaid)").

**Validation.** Test mode exhaustively first; live validation uses a temporary
$1 live Price, never a real $3,900 card. **Build paused at the live step for the
operator's go.**

**Supersedes.** The confirm-before-pay Weekly flow (2026-08-02) and the "matching
NEVER uses email" default (2026-08-01), for the anonymous checkout path only; the
account-anchored stamp path is unchanged.

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
| 2026-08-02 | NAMED COVERAGE GAP: London Police Service has no source anywhere in the fleet (0.1% police share on london.bidsandtenders; no LPS portal/board source). Surfacing on the coverage page awaits the marketing design pass | disjointness probe run 30748625895 |
| 2026-08-02 | Peel drain APPROVED by operator: $54 envelope, all 2,824 peelregion.bidsandtenders docs, triple-duty (police+fire+EMS). York/Durham/London portals stay OUT on probe evidence | awaiting envelope row paste, then dispatch |
| 2026-08-02 | Sunshine+StatCan build GO (design doc approved); collector built, apply blocked until salary-ledger migration pasted | PR pending validation dry-run |

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

## Brief email: phone-fluid now; Free partial folded into G (operator 2026-08-03)

1. PHONE-FLUID (shipped, this pass): render.ts had a fixed 600px wrapper that
   overflowed narrow screens (390px viewport -> 624px scrollWidth = the 600
   column + 24 outer padding). Added a head <style> media query: at
   max-width:600px the wrapper goes width:100% and band side padding drops to
   24px. Phone scrollWidth now 390, no overflow; desktop and Outlook keep the
   fixed 600px. Everything downstream (portal [week] view, public sample C)
   inherits it.

2. FREE PARTIAL IS PART OF G, not a separate track. G is the free path END TO
   END: capture, confirm, welcome, AND the partial brief that lands each Monday.
   A confirmed free list with nothing tier-appropriate to send is half a
   product. Order unchanged: A, then G (partial inside), then B, D, C.

3. NEW SHIP-GATE (4th, alongside Weekly's builds, saved-items round trip, and
   the resolved arc-row name): the pricing table's "Weekly email -> Partial"
   cell for Free is a claim about something that does not exist yet -- same
   class as the false Weekly rows the verification pass caught. The table
   CANNOT publish with that cell until the partial renderer is live.

4. PARTIAL DESIGN (operator): lock by RELEVANCE, not by count. Order items by
   the relevance score and lock the HIGHEST-relevance ones, so a Free reader
   sees the SHAPE of the market and what they cannot see is the thing they most
   want -- the strongest upgrade prompt. Arbitrary/by-count locking wastes it.
   Locked treatment shows buyer, title and one line, then the unlock link:
   enough to know it matters, not enough to act on.

5. ARCHITECTURE (do not break): the /brief/[week] route serves the SAME HTML as
   the email, so C (public sample) is nearly free once the renderer is right.
   The partial must be a PARAMETER on the one renderer (render.ts), never a
   second renderer.

## Marketing-site copy pass: About Team removed, FAQ hover, Da-Ré rebrand (operator 2026-08-05)

Safe class (marketing-site copy/CSS, no schema, no member surface, full
suite green, no new silent-failure path). Shipped in PR #158 (squash
0181c08).

1. ABOUT — TEAM SECTION REMOVED. Operator: "remove the founder about page...
   keep the rest of the about page just not the team section." Dropped the
   portrait placeholder + the whole Team band from about/page.tsx. Rails
   renumbered 01 The mission / 02 What we stand on / 03 The Principle (was a
   four-rail layout with the founder bio). Nothing else on the page changed.

2. FAQ MORE HOVER-INTERACTIVE (operator). site.css: a hovered <details> now
   previews its open state -- white lift + inset red bar
   (box-shadow: inset 3px 0 0 var(--red)) + summary padding-left:16px, the
   ::after marker goes red and scale(1.3). prefers-reduced-motion resets the
   transitions. Same treatment on [open] so hover reads as a preview of the
   click.

3. SYNAPSE ADVISORY -> DA-RÉ ADVISORY (operator: "rebranded... fix it
   everywhere"). 44 references across SiteFooter.tsx, about/page.tsx,
   design-handoff HTML snapshots, docs (ROADMAP, wave3-portal-design,
   legal-seam-investor, client-facing-gate path refs, analyze_solgen_grants
   docstring). docs/synapse-drafting-engine.md git-mv'd to
   docs/da-re-advisory-drafting-engine.md with a "formerly" note. Applied
   migrations (2026-07-10_prospects_seed.sql + two note fields) LEFT UNTOUCHED
   as historical record; the two prospects seed-note DB fields still read
   "Synapse" -- offered the operator a data UPDATE if wanted, open question.

## About stat subline: interval-timing claim pulled (operator 2026-08-05)

Gated class (marketing-site copy), operator-directed and wording approved
via question. The "Years of disclosed award history" stat carried the
subline "Enough depth to measure how long each organisation actually takes
between decision and tender." That is a capability claim the product no
longer makes: the calibration work showed decision-to-tender intervals are
NOT reliably derivable at the organisation level, and predictive interval
timing was removed. Same defect class as the false Weekly rows -- a claim on
a public surface the product can't back.

Replaced with: "Enough history to compare what different organisations have
paid for the same work, going back years." States what the depth genuinely
gives -- cross-buyer disclosed VALUES across years -- fully backed by the
award value data.

The operator's own candidate ("...and when contracts come back to market")
was NOT shipped: return-to-market timing leans on contract end dates, and
0 of 548 awards carry one (end-date extraction backlog, task #56), so that
clause would reintroduce a claim the data can't support -- and return-timing
is adjacent to the very interval capability that was pulled. Operator chose
the value/comparison-only wording. The stat VALUE (dynamic, ~14 years) is
real and unchanged; only the subline moved.

## Brief renderer: corpus-statistics exhibits removed permanently (operator 2026-08-05)

Standing editorial rule. The standing-exhibit bar chart (the Peel / award-
volume "Standing Exhibit" card) is removed from the member-facing brief
entirely and permanently. In operator previews these corpus-statistics
visualizations were useful diagnostics; in a member-facing brief they add no
intelligence value and read as the brief explaining itself rather than
reporting the market. A vendor reading Monday morning does not need to know
how many documents we processed. The brief's job is the arc and the sourced
record; everything else is noise.

Removed: the `Exhibit` type and `BriefView.exhibits` field, `exhibitRow` /
`exhibitHtml` in render.ts, the exhibit band in `renderBrief`, the exhibit
block in `renderBriefText`, and `buildAwardExhibit` in view.ts. The quiet-week
copy (HTML + text) no longer points at "the standing exhibits" -- it now
stands on its own ("We report what the record holds and do not manufacture
items to fill space").

Locked with a permanent test in render.test.ts: the renderer must never emit a
"Standing Exhibit" / by-quarter chart, and an exhibit object force-injected
onto the view renders nothing. Full brief suite green (120 lib tests), web
build clean.

## About/home marketing polish: callout hover + two-sides 2x2 (operator 2026-08-05)

Gated class (marketing-site), operator-directed. Two cosmetic fixes:

1. CANADIAN CALLOUT HOVER. The about page "Canadian-owned and operated" navy
   callout is now interactive. Moved off inline styles into
   `.sn-site .about-ca-callout` in site.css so a hover box-shadow isn't blocked
   by an inline one. Hover lifts the card (translateY -4px) and surfaces a red
   left edge (inset 4px var(--red-on-dark)) plus a deeper shadow -- the same
   red-accent language as the FAQ hover. prefers-reduced-motion resets it.

2. TWO SIDES = 2 x 2, never 3 + 1. The homepage "One market, two sides of the
   table" point-grid used auto-fit, which dropped the fourth card alone onto a
   second line at content width. Fixed to `repeat(2, minmax(0,1fr))`
   (collapses to one column <=640px). A single row of four was considered and
   rejected: the longest nowrap heading ("Every contract in your category")
   clips at a quarter-width track, so two columns is the honest fit. Verified
   by screenshot: clean 2 x 2, no clipped headings, callout lifts with the red
   edge on hover.

## Missing-data sweep: no live surface claims contract-expiry timing (operator 2026-08-05)

Operator: "we shouldn't have anything leaning on that missing data." The
missing data is municipal contract END dates (0 of 548 awards carry one,
task #56). Swept every marketing/product surface for claims that assert we
know when a contract expires / recompetes / comes back to market.

FIXED (live homepage, web/app/(site)/page.tsx, "two sides" panels):
- Supplier card 1 subline "...and when it comes back to market" ->
  "...and the full award history behind it" (backed by the award record).
- Agency card 4 "Your recompete calendar / Every agreement approaching
  expiry, in one place" -> "What your peers are tendering / Open solicitations
  across services of your size, as they post" (backed by tender notices we
  collect now). The recompete/expiry capability is not live and (municipally)
  not backed.
- Synced the two matching point cards in the design-handoff index.html so the
  copy the live page mirrors is clean and can't be reintroduced.

KEPT (not leaning on the missing data):
- Pricing "Expiring contracts (federal)" row: the operator's scoped
  2026-08-03 exception, federal-only, backed by delivery_date from
  open.canada.ca proactive disclosure (a real federal source, NOT the missing
  municipal end dates), governed by the pricing table's ship-gate discipline.
- brief_copy.py "recompete" lines: they tell the reader to note the
  buyer/category to be positioned for the eventual recompete and assert NO
  date -- the honest framing, not an expiry claim.
- main.py / relink_vendors.py: internal code comments, not user-facing.

FLAGGED, not touched: the design-handoff caps illustrative panels (05
"Recompete calendar / Nearest expiries", 01 "Ends 2030" sample rows) are
frozen design-exploration mock data already removed from the live product;
left as-is pending an operator call on whether the mock should be scrubbed.

## Logo mark: compass arrow -> maple leaf (operator 2026-08-05)

Safe class (web-only presentation, no schema, no member data). The compass
arrow mark is replaced by a maple leaf. Wordmark "Signal North" and sub-label
"PROCUREMENT INTELLIGENCE" are unchanged -- mark-only.

SCOPE: web app ONLY. The mark is the single path in BrandMark
(components/site/SiteHeader.tsx), rendered in the site header (22px), footer
(20px), and login/join/thank-you (34px); plus the duplicated path in
components/portal/DashHeader.tsx (portal, 22px). All white-on-navy via the
`fill` prop; navy-on-off-white verified to render cleanly for future use.

EMAILS + BRIEF: deliberately NOT touched. They keep the text serif wordmark
lockup, no image mark. Operator's standing reason: Outlook blocks remote
images, and a broken-image icon in the first email we send is worse than no
image. So there was never a compass image or a local path in the templates or
render.ts to swap -- the "brief renderer references a local path" premise did
not match the code.

SIMPLIFIED SILHOUETTE (operator directive): derived a clean geometric maple,
NOT the detailed realistic leaf supplied -- fine serrations and a thin stem
would muddy at the 20-22px header/footer sizes. VERIFIED FINDING: a truly
STEMLESS maple silhouette reads as an 8-point starburst, not a leaf, at every
size (~15 derivations). The stem is the cue that disambiguates leaf from star.
Operator chose a short STUBBY stem over pure no-stem so the mark actually reads
as a maple. Final path (viewBox 0 0 96 96), kept in sync across both files:
  M48 4 L56 22 L73 16 L70 33 L90 34 L60 50 L70 62 L52 60 L48 84 L44 60 L26 62
  L36 50 L6 34 L26 33 L23 16 L40 22 Z
Verified in situ: header, footer, login (34px) white-on-navy, plus a standalone
both-contexts render. Portal DashHeader is the identical path/treatment.

EMAIL PNG HOST (future reference, operator-agreed 2026-08-05): IF a leaf image
is ever added to email, host the PNG in a Supabase Storage PUBLIC bucket, not
web/public. Reason: the site middleware gate would redirect a /public asset to
/login while the portal is dark, and email clients are unauthenticated; a
Supabase public bucket URL is gate-independent and stable. Not doing it now.

## Logo mark: real maple leaf replaces the hand-drawn one (operator 2026-08-05)

Supersedes the previous entry. The operator rejected the hand-authored
geometric mark ("looks like shit") -- it read as a starburst, not a leaf
(confirmed: a stemless simplified maple is geometrically a star). Directive:
use an actual maple leaf from the internet.

NOTE: the "PNG I gave you earlier" was not retrievable -- the only file that
landed on disk (/root/.claude/uploads/.../IMG_5748.png) is a GitHub Actions
failure-notification screenshot (Daily CanadaBuys run 2d6ae88), not the leaf.
The leaf images rendered inline in chat but were never saved as files. Operator
also authorised sourcing from the internet, so:

MARK NOW: a real maple-leaf silhouette from game-icons.net, author **Lorc**,
licensed **CC BY 3.0**. Single solid outer path (source's interior vein detail
dropped for small-size cleanliness), viewBox 0 0 512 512, coloured via the
BrandMark `fill` prop. Verified in situ (header 22px, login 34px) white-on-navy
and standalone navy-on-off-white across 20/22/34/64/96px -- reads as an actual
maple leaf at every size.

NOT the official Canadian flag leaf: that is protected under the Trade Marks
Act (Dept. of Canadian Heritage) and unsafe as a commercial brand mark. A
generic botanical maple avoids that.

SURFACES (deduped): SiteHeader.tsx now exports MARK + MARK_VIEWBOX as the
single source of truth; DashHeader.tsx imports them (no duplicated path).
web/public/brand/logo-symbol-{white,navy}.svg and web/app/icon.svg (favicon)
were ALSO updated -- PR #164 had missed these three static assets, which still
carried the old compass path.

ATTRIBUTION OBLIGATION (CC BY 3.0): a credit is required and must be reasonably
visible to users, e.g. "Maple leaf icon by Lorc, game-icons.net, CC BY 3.0" in
a site colophon/credits or footer. Recorded here + in SVG comments as the
minimum; a VISIBLE credit line is a marketing-surface change still to be
placed. If the operator wants zero attribution, swap for a CC0/public-domain
maple (harder to source under the current egress allowlist) or commission art.

## Logo mark: official Canadian flag maple leaf, operator-APPROVED (2026-08-05)

Supersedes the game-icons/Lorc leaf, which the operator rejected. New standing
rule from this round: the operator APPROVES the mark before it ships (they now
approved this one explicitly before any code changed).

MARK NOW: the official Canadian flag maple leaf -- the precise 11-point flag
geometry with rounded lobe tips -- taken from a PUBLIC-DOMAIN flag SVG
(hampusborgos/country-flags, svg/ca.svg; flags are public domain). PUBLIC
DOMAIN => no attribution obligation anywhere (unlike the previous CC BY 3.0
game-icons leaf; that obligation is now gone). The leaf subpath was lifted from
the flag's white-square path, made a standalone absolute path, and the viewBox
cropped tight to its bounding box (measured via getBBox): "2463 78 4675 4675".

Matches the operator's reference image. Verified in situ (header 22px, login
34px) white-on-navy and standalone navy-on-off-white at 20/22/34/64/120px.

TRADEMARK NOTE (raised, operator directed anyway): the official flag itself is
protected under the Trade Marks Act for use "in connection with business
activities" (Dept. of Canadian Heritage). A standalone maple-leaf logo is
common commercial practice and distinct from flying/representing the flag;
operator chose the flag-accurate leaf with this noted.

SURFACES: SiteHeader.tsx MARK + MARK_VIEWBOX (single source of truth);
DashHeader imports them; public/brand/logo-symbol-{white,navy}.svg and
app/icon.svg (favicon) all updated to the flag leaf + tight viewBox.

## Logo mark: viewBox fix -- top spike was clipped (operator 2026-08-05)

Operator reported the flag leaf's top was cut off. Cause: the earlier tight
viewBox ("2463 78 4675 4675") was computed from getBBox, which mis-measured
this arc-heavy path (it reported the leaf top at y~400; the true top spike sits
near y~50 in the flag geometry, and the stem also extended below the reported
box). So the crop clipped the top point. Fixed by framing to "2260 -140 5080
5080" -- even headroom around the top spike, balanced margins, verified in the
header. Approved leaf PATH is unchanged; only the framing/viewBox moved. Applied
to SiteHeader MARK_VIEWBOX (single source) + the brand SVGs + the favicon rect.

## Safe-class: eScribe adapter wired to board_minutes + Niagara/Ottawa boards parked (2026-08-06)

Niagara RPSB and Ottawa PSB wired through the eScribe html-mode adapter
(`collect_escribe_board`); both remain `enabled=False` pending `fleet_validate`
results (see probe results in evening digest). London PSB confirmed clean by
fleet_validate (3 meetings / 17 docs); its board_minutes dry-run is next before
enabling. Merged in PR #176 (commit 61b40b5). Safe class: src/ only, no schema,
no member surface, test-covered.

---

## Safe-class: bids&tenders _REF_PAT extended for 4 held tier-2 buyers (2026-08-06)

Four held buyers (Markham, Niagara, Halton Hills, Mississauga) returned 0
parsed rows despite the grid rendering correctly. Root cause: `_REF_PAT` in
`src/tenders_bidsandtenders.py` did not match their ref formats: `135-T-26`
(3-digit-letter-digit), `2026-T-103` (year-letter-number), `2026-047-PQ`
(extra dash-letter suffix), `PRC005534` (prefix+digits no dash). Fixed by
adding four new alternates to `_REF_PAT`; 8 new test cases added and passing
(489 total). Merged in PR #176 (commit 5358006). Safe class: src/ only, no
schema, no member surface, tests cover the fix.

---

## Outage + fix: captured_construction enum missing (operator 2026-08-06)

daily-collect's 06:17 ET scheduled run failed (05 + 06 Aug) with Postgres
22P02: invalid value "captured_construction" for enum processing_status, then
"Run finished with failures in: tender notices, award notices". Healthcheck
fired /fail (loud failure worked).

ROOT CAUSE (mine): the Corridor civil-works holdback (src/filters.py
document_status()) writes status='captured_construction' for construction-only
docs, shipped on the belief that documents.status was unconstrained text. It is
NOT -- it is the `processing_status` enum. So every run that captured a
construction-classified tender/award doc had its insert rejected and the whole
collector run went down. The holdback shipped ahead of its schema -- exactly the
"tell me before capture-all's first expensive morning" case the operator flagged.

FIX (operator approved option a, 2026-08-06): migrations/2026-08-06_captured_
construction_status.sql adds 'captured_construction' to the enum (idempotent,
resolves the type from documents.status, same pattern as the 2026-07-11 /
2026-07-26 enum adds). Applied by paste in the Supabase SQL editor (the standing
migration mechanism). Corrected the false "unconstrained text, no migration"
comment in src/filters.py. No permanent data loss: daily-collect is
content-hash idempotent, so the held-off docs are re-collected on the next run
after the paste.
