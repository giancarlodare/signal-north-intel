# Signal North methodology doctrine

The operating discipline of this shop, stated domain-agnostically. Signal
North (Canadian public-safety and defence procurement) is the first
instance; the doctrine is not about procurement, policing, or Canada. It is
about how an intelligence product earns the right to be believed.

Status: STANDING. Updated as the discipline evolves. Written 2026-07-28 at
the operator's instruction, because this is the shop's most portable asset
and it had been living in practice and in working memory rather than on
paper.

---

## 0. The premise

An intelligence product's only durable asset is that a skeptical expert,
checking our work, finds it holds. Every rule below is downstream of that.
Speed, coverage, and cleverness are worth nothing if a chief, an analyst,
or a competitor can find one fabricated date, one broken provenance link,
or one number that cannot survive its own footnote.

We would rather ship less and be trusted than ship more and be checked
once, badly.

---

## 1. Access discipline

**Robots is honored absolutely, never scraped around.** A `Disallow` on the
path we want is a closed door, not an obstacle. We do not switch user
agents to evade a ban, do not route around a block, and do not treat "the
page renders publicly in a browser" as permission. A robots-walled source
becomes a *disclosed coverage boundary* (section 7), never a quiet scrape.

Corollaries:
* robots.txt is fetched and **printed verbatim** in the probe record before
  any collection from a new host, so the verdict is auditable later.
* A 4xx on robots.txt is allow-all per RFC 9309; a 5xx is treated as
  disallow (fail closed).
* We identify ourselves honestly in the User-Agent. When a name change is
  needed it must be because our name causes a FALSE match (e.g. a token
  that collides with an unrelated banned tool), never to escape a rule
  aimed at us. The distinction is the whole ethics of it: clearing a false
  collision is honest, evading a true block is not.
* Politeness is not optional: one shared delay between requests, declared
  `Crawl-delay` honored, per-run caps so a backfill never hammers a
  publisher.
* Where a publisher's terms require a relationship rather than a crawl, the
  answer is to ask them, not to take it. Outreach is a business decision
  with its own gate, not an engineering shortcut.

## 2. Provenance discipline

**Every item links to its own publisher record, and the link never
over-claims.**

* Provenance is the PUBLISHER's URL, not a cache, not an aggregator, not
  our own transport endpoint. If we read an item from an API, the
  provenance is the human-facing page the publisher offers, not the JSON
  call.
* Link labels must match what the click actually delivers. We classify
  every stored URL as **record** (a real per-item page), **listing** (a
  publisher page listing many items, deep-linked as far as the publisher
  allows), or **portal** (a landing page where the item is locatable by its
  reference). The label says which. "View the publisher record" is a
  promise; it is only made when it is kept.
* When only a portal-level link exists, the publisher's own **reference
  number** is surfaced beside it, so the record is reachable in two clicks.
* We never fabricate a deep link that the publisher does not offer.

## 3. Honesty of data

**None beats a wrong value.** A missing field is information; a plausible
invented one is a liability.

* Dates: never fabricate a day. Stored precision is respected on render
  (month precision renders "Apr 2026", never "1 Apr 2026"). An unparseable
  date is NULL, and NULL is displayed as absence, not guessed.
* Identifiers: the publisher's own key, verbatim. We normalize whitespace
  and nothing else. We do not reformat, pad, or invent references.
* Amounts, timing, organizations: extracted only when the source states
  them. "The document does not say" is a valid and frequent answer.
* Names resolve to canonical entities by exact (normalized) match plus
  curated aliases, never by fuzzy substring, because a wrong attribution is
  worse than an unresolved one. Unresolved is flagged and visible.

## 4. Failure discipline

**Loud failure over silent empty.** The failure that costs the most is the
one that looks like a clean zero.

* A collector that reads a live source and finds nothing RAISES. A live
  portal essentially always has rows; zero means we were gated, or the
  markup changed, or the endpoint moved. Silence is never recorded as
  truth.
* Legitimate emptiness must be PROVEN, not assumed: the escape hatch is the
  source's own count endpoint confirming zero, not our failure to find
  anything.
* Query errors never degrade to empty results. A failed read throws; it
  does not return `[]` for a renderer to display as "no items." (Learned
  expensively: a bad column name once 400'd every page load for a day while
  the UI showed a confident, wrong "0 items.")
* Per-item resilience with a systemic tripwire: one bad row is logged and
  skipped, but a PILE of failures exceeds an error budget and aborts the
  run loudly.
* Guards are written to survive their own absence: a pass that depends on a
  not-yet-applied migration self-skips with a clear notice rather than
  reddening an unrelated pipeline.

## 5. Build discipline

**Design-first, always in this order:**

    probe -> design doc -> operator approval -> build -> validation bars -> go

* **Probe** before designing. Never assume a source's structure, robots
  posture, or reachability. The probe runs in CI from a clean environment
  and its output is the evidence record.
* **Design doc** before building: the access method, the identity/dedupe
  key, the mapping to the spine, the loud-failure guards, the cadence, the
  cost, and the explicit decision points the operator must rule on.
* **Approval** is per source and per enablement, not blanket.
* **Validation bars** before anything goes live: a dry-run table with the
  real measured numbers (rows read, parse rates per field, distribution,
  samples). Enablement is a decision made against that table, never against
  a hope.
* **Diagnose and extend, never enable-and-hope.** A source that fails its
  bars is HELD with a written verdict, not enabled with a shrug.
* Nothing enables itself. Collection turns on when a human pastes the seed
  and says go.

## 6. Cost discipline

**Measured envelopes before spend.**

* Any bulk or historical processing gets a projected envelope BEFORE
  dispatch: measured per-unit rate times counted units, stated as a range,
  approved explicitly.
* Envelopes never auto-extend. A cadence does not quietly grow into a
  drain; new scope pauses for a new approval.
* Actual spend is measured from real usage counters and reported against
  the envelope when the work completes. We do not estimate after the fact.
* Steady-state spend is capped and known; unbounded work is gated by
  construction.

## 7. The client-facing gate

**Anything shown to a client must be defensible to a skeptic, or withheld.**

* The test is not "is it caveated" but "would it survive scrutiny." A
  number that needs an apology should not ship. **Never caveat what should
  be withheld.**
* Statistical claims pass a significance gate before publication, and the
  gate is designed to say no. When an estimator collapses to a boundary
  (heterogeneity not estimable, insufficient local data), the honest output
  is "not estimable", never a sector average dressed as a local figure.
  **Zero honest cells beat one dishonest cell.**
* Derived and pooled figures are NEVER rendered in the same register as
  direct measurements. Provenance labels on derived numbers are
  non-negotiable, so a reader who later learns how a number was made finds
  it was labeled that way all along.
* A **human release gate** sits above every statistical gate. Clearing the
  math is necessary, not sufficient; a person decides what becomes
  client-visible.
* Coverage is stated honestly, including its holes. A disclosed boundary
  ("this jurisdiction's direct tenders are behind a robots wall; here is
  the proxy we do have") is an asset. An implied completeness we cannot
  back is a liability.
* Product surfaces claim only what is live. Roadmap features are labeled as
  roadmap on the pricing table itself, never checked as if shipped.

### 7.1 Earliness is a claim about the record, not about the future

The line the whole product rests on, and the one most easily blurred:

> **"Months before the solicitation" is a claim about when the public
> record exists. It is not a claim about our ability to time a future
> event.**

A budget line, a board decision, a staff report and a capital plan are
published months before the tender that follows them. Saying so asserts
nothing about the future: it is a statement about documents that already
exist, each of which we can link. Saying "the tender lands in Q1" is a
different kind of sentence entirely, and it needs a statistical apparatus
that has to earn its way past the significance gate first.

Both sentences sound like earliness. Only one is free. The test on any
draft copy is mechanical: **strike the sentence and ask whether what
remains still points at a document a reader can open.** If yes, the claim
was about the record. If the sentence was doing the work on its own, it
was a forecast wearing the record's clothes, and it comes out.

Applied consequences:

* Named comparables replace modelled intervals. "Four other services ran
  this sequence; here are their dates and their links" is a measurement of
  the past. "The measured interval implies February" is a projection.
* A comparable set with fewer than two genuine members returns nothing,
  and the item stays a record item. **Thin arcs are worse than no arcs**:
  one comparable reads as a pattern while being an anecdote.
* Every narrative element carries a disconfirming line, naming what would
  stop the sequence completing. Content marketing omits it; a defensible
  record cannot.
* Statistical machinery is retained as an INTERNAL instrument (prediction
  ledger, significance gates, pooled estimators). Internal use does not
  require a product claim, and a product claim is not licensed by internal
  use.

## 8. Security and access-control posture

* The database is the gate, not the UI. Row-level policies enforce what a
  member may read; application filters exist for faithfulness of preview
  and clarity, never as the security boundary.
* Fail closed by default: an absent flag means invisible, an absent role
  means least privilege, an unset feature flag means the surface does not
  exist.
* Prefer a purpose-built projection over widening a policy on a rich table.
  A flat table containing only gate-cleared presentation columns cannot
  leak what it does not contain, and its gate lives in one reviewable,
  testable file rather than in policy predicates spread across tables.
* Independent barriers over a single clever one: the member-visibility flag
  is derived by a pass that shares no code path with the composition lens,
  so a break in one cannot silently open the other.

## 9. Editorial discipline

* The corpus is keep-all; the LENS is what selects. Filtering happens at
  composition, never by destroying signal.
* Selection bars are explicit, versioned, and reported (what was in-window,
  what cleared the bar, what was held and why).
* Held items are written as held, one toggle from inclusion, so the editor
  can see what the lens set aside rather than trusting it blindly.
* Prompts are versioned IP: never edited in place, each version stamped
  onto the artifacts it produced, so provenance survives a model swap.
* A prompt or model change ships only if quality holds. Cost savings never
  justify degrading extraction; a measured quality regression is a
  no-ship, full stop.

## 10. Operating posture

* Report honestly: a partial night is stated as partial, a red run is named
  with its cause, and "I was wrong" is said plainly and early. A corrected
  diagnosis is cheaper than a confident wrong one.
* Check first, then act. When a premise can be verified from the code, the
  logs, or a probe, verify it rather than reasoning from memory.
* All operator-facing times are in the operator's timezone, never UTC.
* No em dashes in generated copy.
* Every deliverable ends with what the human must decide.
