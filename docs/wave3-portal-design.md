# Wave 3: subscriber portal (staged-dark design)

Status: DESIGN for operator approval (sprint front 7, 2026-07-25). STAGED-DARK
by contract: everything below is built behind auth and feature flags, nothing
is public, no marketing claim ships, Stripe stays in test mode until the
operator flips it live in a separate decision.

Governing doctrine: THE CLIENT-FACING GATE (docs/client-facing-gate.md)
binds every member-visible surface here. The dashboard read layer shows
only gate-cleared items; not-confident-enough means withheld, never
caveated forward.

## Scope

A founding-member-facing portal over the existing corpus and prediction
ledger. Five pieces, in dependency order:

1. **Marketing site (dark).** A static landing page describing the product
   (predictive government-procurement intelligence, provable track record).
   Built and deployable but behind a noindex/robots-disallow and not linked
   from anywhere public until launch. No pricing claims, no testimonials, no
   fabricated numbers; copy uses only figures the ledger can substantiate.
2. **Auth.** Email + magic-link (or password) via Supabase Auth, which the
   stack already provides. Row-level security scopes every read to the
   member's own account. Founding-member accounts are provisioned manually
   (no open signup while dark).
3. **Dashboard + tags.** The read-only member view over signals/procurements:
   the same event-date-first, provenance-linked rows the internal review page
   shows, filtered to what a subscriber may see (published briefs, not raw
   triage). Tag chips (defence_relevant, jurisdiction, buyer, timing path)
   drive filtering. Renders month-precision dates as "Apr 2026", never a
   fabricated day (the standing date-precision rule).
4. **Functional watchlist with event logging.** A member follows buyers /
   vendors / keywords; the watchlist stores the follow and LOGS every match
   event (what fired, when, which signal) to an append-only table. The event
   log is the substrate for later "we told you first" evidence and for
   usage analytics; it is provenance-clean (each event points at a real
   signal + its publisher URL).
5. **Stripe (test mode).** Checkout and subscription plumbing wired against
   Stripe test keys only. No live charge is possible while dark. The billing
   seam is isolated so going live is a key swap plus an operator decision,
   reviewable on its own.

## Firewall and legal alignment (already recorded, restated here)

- The investor-facing export seam (docs/legal-seam-investor.md) stays dark and
  gated; the portal is the SELLER audience, isolated at the export layer.
- Synapse Advisory (docs/ROADMAP.md) consumes the portal's published outputs
  as any subscriber; no reverse flow. The founding-member Synapse benefit is
  a cross-entity perk with separate paper (September counsel question).

## What is deliberately NOT in this wave

- No public signup, no live billing, no marketing distribution, no investor
  surface, no auto-generated claims. Predictions are shown as the ledger
  records them (confirmed/probable/speculative), never as advice.

## Build shape on approval

Design-first still applies: this doc is the proposal. On go, the build is a
staged sequence (auth + RLS, then dashboard read, then watchlist + event-log
table migration, then Stripe-test), each its own PR with tests, all behind a
`PORTAL_ENABLED` flag defaulting off so nothing renders publicly until the
operator flips it. The event-log table is the one schema addition; everything
else reads the existing corpus.

## Banked post-pilot: the convergence indicator (operator 2026-07-26)

When the predictive layer's pilot proves significance (Toronto + Peel; gate
and full spec in docs/demand-arc-backtest-design.md section 0d), the
dashboard (piece 3) gains a per-service, per-domain CONVERGENCE INDICATOR as
a first-class view next to the watchlist:

- rises as independent upstream signals stack on the same service + domain;
- always shows the specific converging signals, each provenance-linked
  (never a black box);
- attaches the expected movement window from that service's measured
  demand-arc lag, with the cell's CI as the confidence band; a pending cell
  shows convergence WITHOUT a window (honest gaps reach the client surface);
- sharpens the predicted instrument (grant / tender / legislation / program
  change) as more signals land; each sharpening step is dated and logged to
  the same append-only event log as watchlist matches.

Design-thinking only: recorded here so the dashboard and event-log schema
anticipate it. NOT built ahead of the pilot gate, and its build is its own
operator-approved stage when the gate opens.

## Banked post-pilot: the interactive prediction pathway (flagship visualization, operator 2026-07-26)

The flagship visualization of the predictive layer. GATED on the predictive
engine being solid: the pilot must prove arcs reconstruct cleanly, the
demand-arc rhythms must be real (PUBLISHED cells), and per-node provenance
must verify. Build the engine first, then this window onto it. NOT built
ahead of that; recorded here as design intent so the dashboard anticipates
it.

Click a prediction and it expands into an interactive horizontal timeline of
the reconstructed arc, three layers:

- **(a) The real events, in sequence.** Each node is a real event from the
  arc, categorized by intel type (news -> council motion -> premier comment
  -> councillor statements -> council resolution -> city budget line ->
  police budget line), and each node CLICKS THROUGH to the real source
  document. Provenance is the credibility: the client can read every
  underlying document themselves.
- **(b) The measured rhythm, above the flow.** Between each phase, the
  statistically significant average lag from the demand-arc engine (the
  PUBLISHED cell for that transition), so the client sees the service's
  historical rhythm and that THIS arc is tracking it.
- **(c) The projection, extending into the future.** A line continuing past
  the last real event to the predicted outcome, with confidence drawn as a
  WIDENING CONE. The cone IS the confidence interval: uncertainty is
  visualized, not caveated, exactly per the client-facing gate's
  withhold-not-caveat corollary.

Why it is the flagship: the prediction becomes self-justifying (the UI shows
its work), and it displays the multi-source, multi-year provenance trail
competitors cannot replicate without the corpus and the linking machinery
behind it.

STRICTLY DOWNSTREAM by design. It visualizes the linked arc; it computes
nothing of its own. Hard prerequisites, all three: (1) verified arc
reconstruction (the propose-then-approve proposer loop, operator-confirmed
links); (2) real significance rhythms (PUBLISHED demand-arc cells for the
transitions shown; a pending transition shows no rhythm number); (3)
per-node provenance verification at render time. A node linking a wrong
source is worse than no timeline: one bad click-through discredits the whole
surface (the trust asymmetry in docs/client-facing-gate.md), so every node
passes the signal gate before the timeline renders, and an arc with an
unverifiable node renders no timeline at all.

## BUILD GO: stages 1-4 (operator 2026-07-27), with the design boundary

Engineering go for stages 1-4, stage 1 starting Mon Jul 28 after the
ten-buyer collect is verified clean. Design-first PER STAGE: each stage's
decision points and table go to the operator BEFORE its PR merges.

FIRM BOUNDARY (operator instruction, binding on every session): NO
design, styling, visual, or artistic work, and NO marketing copy, in
this build. Giancarlo does all design separately in Claude Design and
hands over files to incorporate. The build delivers the FUNCTIONAL layer
fully and stops at unstyled functional skeletons for anything visual,
with clean separation of logic from presentation so design files drop in
later. Stage 5 (marketing site) and all dashboard visuals are AWAITING
GIANCARLO'S CLAUDE DESIGN FILES; do not start them.

Stage specifics as instructed:
1. Member auth + RLS: member vs operator roles; the RLS policies ARE the
   client-facing gate (docs/client-facing-gate.md): member reads scoped
   to published + gate-cleared surfaces only, enforced by the DATABASE,
   not the UI. PORTAL_ENABLED flag plumbing, defaulting off. Operator
   pastes the DDL.
2. Dashboard: member-filtered data layer + functional component skeleton
   over published briefs and gate-cleared signals, unstyled, ready to
   receive design.
3. Watchlist + event log + saved items (scope extended, operator
   2026-07-27). Two DISTINCT per-member data models, both owner-scoped by
   RLS (a member reads/writes ONLY their own rows: this extends the
   client-facing gate from read-only gate-cleared surfaces to per-member
   OWNED data):
   a. **Watched keywords / tags (forward-looking).** A member follows
      buyers / vendors / keywords / tags; the daily pipeline runs a
      deterministic (no-LLM) match-event writer that LOGS every FUTURE
      signal matching a watch to an append-only event log (what fired,
      when, which signal + publisher URL). This is the "we told you
      first" substrate. Tables: `member_watches` (the standing follows) +
      `watch_events` (append-only matches).
   b. **Saved / bookmarked items (point-in-time).** When a member flags a
      Weekly Signal item they like, it saves to their personal saved
      list. This is NOT a watch and NOT an event-log entry: it is a
      manual bookmark of an item that already exists, with no matching
      logic and no event stream. Folding it into the event log would
      fabricate "match events" for a manual action and pollute the
      "we told you first" trail. It gets its own small join table,
      `saved_items` (member_id, brief_item_id, saved_at), owner-scoped by
      RLS. Launch scope saves Weekly Signal items (brief_items);
      signal-level saving from the raw feed is a later extension.
   Operator pastes the DDL for all three tables.
4. Stripe test mode: checkout/subscription plumbing against operator-
   provided test keys. No live-charge path while dark.

## Member surface for launch and two scoping decisions (operator 2026-07-27)

The BUILD-NOW member surface is the dashboard, comprising: dashboard home,
the brief / signal feed (stage 2, functional skeleton built), a saved /
bookmarked-items view (stage 3b), and watched keywords / tags that flag
matching future signals (stage 3a, the "we told you first" event). The
public-safety member-read gate (docs/public-safety-relevance-filter-design.md)
sits under all of it. All of it stays behind PORTAL_ENABLED.

Two scoping decisions, banked:

1. **NO drag-and-drop / customizable dashboard for launch.** Ship a
   well-designed FIXED layout first; add rearrangement later once real
   founding members tell us what they would move. Building configurability
   before there are users is guessing. (Design of the fixed layout is
   Giancarlo's Claude Design work, per the firm boundary above.)
2. **Automated grant-application tooling is NOT a member-facing Signal
   North feature.** It is internal / Synapse-side service delivery, kept
   across the neutrality wall (docs/legal-seam-investor.md, ROADMAP
   firewall). Members wanting grant help are REFERRED to Synapse; they do
   not do grant work inside the neutral product. Do not build grant tooling
   into the member portal.
