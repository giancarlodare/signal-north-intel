# Demand-voice layer — design (operator 2026-08-02; design only, no build)

The gap this closes: everything we collect is the formal record, inside an
administrative process. Nothing captures what is being CALLED FOR, upstream
of a business case. The worked example: public calls for drone-as-first-
responder capability after the Toronto consulate shooting — months ahead of
any procurement document, exactly what a vendor sells against, invisible to
the corpus. A tender means the subscriber is already late; this layer is
where they are early.

## The design's spine: weight by who is asking

Ordering by evidentiary weight is the whole design. Proposed `asker_weight`
dimension on this layer's signals (parallel to, never mixed with,
evidence_grade, which stays a claim about the procurement record):

| weight | asker | examples |
|---|---|---|
| 5 | Institutional ask, accountable author, response expected | Coroner's inquest recommendation; OCPC direction; AG Ontario VFM recommendation; public inquiry |
| 4 | Sector association, on the record | OACP / OAFC / PAO / OAPC pre-budget submission or position paper |
| 3 | Named official of a service | chief's public statement, service release, deputation BY a service |
| 2 | Trade/vendor press | Blue Line, Vanguard, vendor Canadian-entry announcements |
| 1 | Ambient | local incident-and-reaction coverage, residents quoted |

Weight 1 is CONTEXT: collected, linkable, never surfaced as a standalone
item. A resident quoted in an article is atmosphere; a jury addressing the
Solicitor General by name is a signal.

## Sources (ranked, with collection posture)

Layer members, robots verdicts from the coverage probe run (see the
coverage report for the measured table):

1. **Coroner's inquest recommendations** (ontario.ca, verdicts-and-
   recommendations pages). Public, dated, addressed to named services with
   expectation of response. Strongest single source; publishes continuously
   at low volume. The RESPONSES (services answering the jury) are
   themselves commitment-grade material.
2. **Pre-budget submissions** (OACP, OAFC, PAO, OAPC; provincial and
   municipal). Annual, literally a list of asks.
3. **Association position papers / statements** (same four sites).
4. **OCPC reports; AG Ontario VFM audits** touching policing/fire/EMS;
   public inquiry recommendations.
5. **Council delegations/deputations** on public-safety items — reached by
   the council-agenda adapter (keystone), zero extra collection here.
6. **Chiefs' and services' own releases** — service newsrooms/RSS.
7. **Trade press** (Blue Line, Canadian Firefighter, Canadian Security,
   Canadian Defence Review, Vanguard, Esprit de Corps) — RSS only.
8. **Vendor announcements** — doubles as the foreign-entrant feed for the
   commercial pipeline.
9. **Local news** — weight 1, context only.

## Copyright and robots, non-negotiable

RSS or explicitly permitted feeds only. We store metadata (title, date,
link, source, asker classification) and never reproduce article text on a
member-facing surface; the member reads the publisher, we point. Any site
whose robots or terms forbid collection is reported as a coverage boundary
on the coverage page, not worked around. (CanLII precedent applies.)

## Surfacing: labelled, never blended

A demand-voice item is a different CLAIM from a procurement item: "this is
being asked for" vs "this is being procured." Distinct doc types
(`inquest_recommendation`, `prebudget_submission`, `position_paper`,
`demand_press`), a distinct visual register in the brief, and the asker
weight shown. It never enters the procurement ranking.

## How it scores without swamping the brief

This layer will out-volume everything else we collect. Three containments:

1. **Its own section, fixed budget.** The brief structure the operator
   named: *pressure → money → ask → purchase* (what's being called for,
   what grants are open, what services are formally asking for, what's
   being procured). Each section has its own selection; demand-voice items
   compete only with each other for a capped number of slots.
2. **Weight floor for surfacing.** Weight >= 4 defaults into the brief;
   weight 3 needs a corroborating item (a second asker or a matching grant/
   budget line); weights 1-2 surface only as context links attached to a
   stronger item, never standalone.
3. **Arc composition upgrade.** The demand arc gains a rung BELOW intent:
   `called_for` (rung 1 in taxonomy terms is 'chatter'; an inquest
   recommendation is chatter with an accountable author, so the arc can
   begin at a jury's ask and end at an award). This is what makes
   "pressure -> purchase" one composable story rather than two lists.

## Costs (collect-only)

RSS polling + inquest/association page checks: tens of items/day at peak,
KBs each (metadata only). Storage negligible. No LLM at collection; asker
classification is deterministic from source (the source IS the asker class
for 1-4; only weight-3 statements need any judgment, deferrable to the
extraction budget later, gated as usual).

## Build order (when approved)

1. Coroner inquests + AG Ontario + OCPC (highest weight, lowest volume,
   plain document pages).
2. Association sites x4 (pre-budget season is annual; position papers
   trickle).
3. Trade press RSS (six feeds).
4. Vendor announcements (rides discovery + trade press initially).
Council deputations arrive free with the council-agenda adapter. Local news
already partially exists via Google News coverage monitor, re-labelled
weight 1.

Gated: everything above is a new-source build; nothing collects until the
operator approves this design.
