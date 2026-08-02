# Data-architecture principles (operator 2026-08-02)

None of these are products and none delay launch; all are expensive to
retrofit. They constrain every schema and pipeline decision from here on.

1. **Event-sourcing over state.** Store what happened, not the current
   value. Subscription state, watchlist changes, coverage changes:
   append-only with timestamps.
2. **Immutable, content-hashed document snapshots.** Never overwrite a
   collected document. Portals amend and delete; the diff between versions
   is signal we currently discard.
3. **Instrument the product from the first member, cohort level only.**
   Saves, watchlist adds, searches, click-throughs, alert configs, all
   timestamped. Never expose or make inferable one member's activity to
   another; never attach identity to anything that leaves the system.
4. **Structured editorial decision log.** Every inclusion, exclusion and
   withhold when composing a brief: item, decision, reason code,
   timestamp. Not prose.
5. **Provenance and confidence on every derived claim, universally.**
6. **Relevance is a function of (item, context), never a scalar on the
   signal.** See the addendum.

## Addendum: tier strategy — the engineering parts

1. **Why relevance must be (item, context).** Relevance is a relationship
   between an item and a reader, not a property of an item. A
   records-management renewal is highly relevant to one vendor and
   worthless to another. The lens score being built is already Pro's core
   differentiator: generic relevance ranks the Weekly brief; the SAME
   function with a member profile as a parameter is the monitoring
   product. One argument, not two systems. Nothing builds member context
   now — but nothing may bake in relevance-as-scalar either. The approved
   relevance backfill column is understood as relevance(item,
   generic-context), an evaluation of the function at the generic point,
   not the function itself.
2. **Domains are a personalization axis, never a pricing axis.** Every
   tier gets police, fire, EMS and defence; the member profile is where
   they say which they care about. No tier gate on domain, ever, and
   domain never enters the tier table. Fragmenting by domain would destroy
   the single best story: a radio vendor seeing demand across police,
   fire and EMS in one place.
3. **Free's locked items follow a principled rule.** Order the free email
   by relevance and lock the HIGHEST-relevance items; locking arbitrarily
   wastes the strongest upgrade prompt we have. Lands with the send half.
4. **Enterprise's API returns records scored against the customer's
   profile, not raw records.** Raw records are a CSV export; scored
   records are infrastructure. That distinction is what the Enterprise
   price rests on and shapes the API design whenever built.
5. **One product boundary to hold: Weekly may get filtering, never
   watching.** Filtering what you read is a reading aid, fine at Weekly.
   The system watching on your behalf is Pro. A Weekly filtering feature
   that starts persisting and checking has become Pro and cannibalized
   the tier.

## Coverage-table scope split (same ruling set)

The coverage table carries a `scope` field with two values, so the
coverage page can be generated from it:

* **claimed** — buyers inside what we sell today and don't yet reach
  (Hamilton, Niagara, Ottawa's board, London, Windsor police, the rest of
  the ~44 services). These belong on the page BY NAME.
* **roadmap** — sources that entered the roster later and were never part
  of a coverage claim (base hospitals, vendor rosters, news tiers,
  associations, demand-voice sources). These never appear in a "not
  covered" list, because we never said we covered them.

Without the split, 199 absent rows make a product with complete federal
coverage and seven deep police boards read as covering nothing — same
data, opposite impression, and the second one is accurate.

**Reachability is separate from coverage and never leaks into the page.**
The tcp-timeout hosts are absent because no collector exists, not because
they are unreachable; reachability gates the build queue. Different
questions, different columns. And per the standing rule: cross-run
agreement is the bar for the tcp-timeout class — nothing is marked
permanently unreachable on one run's evidence.
