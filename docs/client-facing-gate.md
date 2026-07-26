# The Client-Facing Gate (governing doctrine, operator 2026-07-26)

Status: DOCTRINE, banked. A design principle that shapes every client-facing
surface (Wave 3 dashboard, Weekly Signal, the Grant Engine, any later API).
Not a build-now item: nothing here is implemented ahead of its surface; the
requirement is that every surface's design carries the gate as a required
component, not an afterthought.

## The principle

Anything a client sees (a signal, a prediction, a drafted application) must
be defensible to a skeptic. There is an explicit backend -> frontend GATE:
nothing crosses until it is true enough to defend. Trust is asymmetric: one
confidently-wrong client-facing item discredits everything after it, while a
hundred right ones only slowly build what one error destroys.

**Corollary: withhold, do not caveat.** Do NOT push uncertainty forward as
endless caveats on the client surface. The confidence work happens on the
backend so the frontend is clean. The answer to "not confident enough" is
WITHHOLD, not caveat. A clean confident frontend is the reward for a
rigorous backend. (This is the client-surface reading of the standing
honesty rules: internally we show pending cells and thin n everywhere,
because the operator needs to see the machine's uncertainty; the client sees
only what cleared the gate.)

## Three gap types to engineer against

1. **COVERAGE gaps.** The system must know its own coverage boundaries and
   never let "we are not looking there" read as "nothing is happening
   there". Design consequence: a per-service / per-domain
   COVERAGE-CONFIDENCE attribute (which sources are collected, how deep,
   how fresh; the collected-vs-available inventory from the
   backward-reconstruction program is its natural input). Client-facing
   claims are BOUNDED to what is comprehensively covered: "no movement at
   service X" is only sayable where coverage confidence supports it;
   elsewhere the surface says nothing rather than implying quiet.

2. **CONFIDENCE gaps.** The significance gate is binary at the client
   surface: only PUBLISHED cells (n >= N_MIN and CI width inside W_MAX) go
   client-facing. "pending, n=X" is INTERNAL-ONLY vocabulary; a client
   never sees a soft number or a half-confident window. (The convergence
   indicator's "convergence shown without a window" case is the one
   designed exception, and even there the withheld window is a withhold,
   not a caveat.)

3. **CORRECTNESS gaps (the dangerous invisible one).** A wrong item can
   pass every confidence check while being factually wrong (bad extraction,
   misattributed org, wrong date, hallucinated figure). The existing
   defenses (calibration audit, loud-failure, none-beats-a-wrong-date,
   propose-then-approve on arc links, provenance-linked publisher URLs)
   extend with a dedicated VERIFICATION LAYER for anything crossing the
   gate: an item bound for a client surface gets re-verified against its
   source document before it crosses, not just at ingestion time.

## Per-surface gate tests (to design into each surface's build)

- **Signals** cross the gate only when: provenance verified (publisher URL
  resolves to the claimed document), extraction confidence above threshold,
  no unresolved organization leaking through (an unresolved org is an
  internal state, never a client-visible one), and a real date (the
  date-precision rules; a NULL date is shown honestly or the item is held,
  never a fabricated day).
- **Predictions** cross only when: the significance gate is cleared
  (PUBLISHED cell) AND every underlying signal in the arc has itself passed
  the signal gate. A published cell built on ungated signals does not
  cross.
- **Drafted applications (Grant Engine)** cross only when: every factual
  claim is traceable to a real source document or verifiable public fact,
  no hallucinated statistics, rubric-scored against the funder's published
  criteria, and HUMAN-REVIEWED before anything is marked client-ready. The
  drafting engine's output is a draft until a human clears it, always.

## Where the gate binds (cross-references)

- Wave 3 dashboard (docs/wave3-portal-design.md): the dashboard read layer
  filters to gate-cleared items; the convergence indicator inherits the
  confidence-gap rule above.
- Weekly Signal (docs/published-brief-design.md): the brief's honesty rules
  are the editorial half of the gate; this doctrine adds the backend half
  (coverage bounding and the verification layer).
- Grant Engine (docs/synapse-drafting-engine.md): the drafted-application
  test above is a required component of its build, whenever that build is
  triggered.
- Predictive layer (docs/demand-arc-backtest-design.md sections 0 and 0d):
  the significance gate is the confidence-gap instrument; Claim 1 / Claim 2
  both cross only through this gate.
- API access (docs/ROADMAP.md): gating condition 1 (no prediction endpoint
  until CIs and track record are real) is this doctrine applied to the API
  surface.

Recorded as doctrine. Nothing to build now beyond keeping it in every
client-facing design.
