# The spine / vertical seam

Operator instruction 2026-07-28: the domain-agnostic machinery may later
power additional intelligence verticals under the same holdco. **Nothing is
extracted into a package today.** The only rule is: stop entangling, so a
later extraction is mechanical rather than archaeological.

## The line

**SPINE (domain-agnostic, portable):** collector framework and politeness
engine, robots discipline, provenance model and honest link labeling,
extraction pipeline and versioned prompt library, loud-failure guards,
identity/dedupe by content hash, the client-facing gate machinery,
validation-bar ritual, cost-envelope discipline.

**VERTICAL (public-safety specific, disposable per vertical):** the keyword
sets, public-safety org types and the relevance filter, the signal-type
vocabulary, demand arcs, the brief lens and its bars, category slugs.

## Standing rule

Before hardcoding a domain term into something structurally generic, stop
and flag it. Prefer: generic mechanism + vertical CONFIG. The existing good
examples are the pattern to copy.

**Good seams already in place (copy these):**
* `src/filters.py` -- generic whole-word matcher (`_word_pattern`) with the
  vocabulary in `config/keywords.txt`. The engine knows nothing about
  policing.
* `src/signal_extractor.py` -- generic extract/resolve/grade/write pipeline
  with the domain knowledge isolated in the versioned prompt library.
  Swapping verticals is a prompt version, not a code change.
* `src/supabase_client.py`, `src/hashing.py` -- pure infrastructure, clean.

## Entanglements found (2026-07-28 audit, NOT being refactored now)

Recorded so a later extraction is a list, not an excavation.

1. **`PoliteFetcher` lives inside `src/board_minutes.py`.** This is the most
   portable component in the codebase (robots.txt per host, RFC 9309
   handling, declared `Crawl-delay` honoring, one shared politeness delay,
   single honest UA) and it sits inside a vertical collector. A later
   extraction wants it as its own module. Highest-value item on this list;
   a pure move, no behavior change.
2. **`src/live_surface.py` (written today)** is a generic projection
   mechanism (gate-cleared slice -> flat presentation table) with the
   vertical slice inline as constants: `LIVE_DOC_TYPES`, the
   `public_safety` predicate, `MIN_GRADE`. The mechanism generalizes; the
   slice should eventually be config passed in.
3. **`web/lib/portal/provenance.ts`** is generic honest-labeling logic with
   platform-specific URL patterns (bids&tenders, Biddingo) inline. The
   classifier is portable; the pattern list is vertical config.
4. **`src/taxonomy.py`** grades evidence from signal types, which is a
   generic idea (rung ordering) expressed in a vertical vocabulary.

## Schema: where public-safety semantics sit on generic tables

The operator's target shape is **entities + relationships + sourced claims
with provenance and confidence**. The honest read is that we are closer
than expected, because `signals` is already nearly that shape:

    signals = a CLAIM, with document_id (provenance), confidence,
              evidence_grade, organization_id (entity link)

What is genuinely generic today: `sources`, `documents`, `organizations`
(an entity table), `signals` (a sourced claim table).

What hardcodes the vertical onto those generic tables:
* `signals.public_safety`, `signals.defence_relevant`,
  `documents.defence_relevant` -- vertical booleans as columns
* `signal_type` enum VALUES -- a vertical vocabulary in a generic
  "claim type" slot
* `organizations.org_type` VALUES (police_service, police_board,
  corrections) -- vertical vocabulary in a generic entity-type slot

What is missing for a true generic graph (do NOT build now):
* **relationships are not first class.** Today they are implicit
  (signal -> org, signal -> document) or bespoke joins
  (`procurement_signals`). A second vertical wants a generic edge table
  (subject, predicate, object, sourced-by, confidence).
* **entities are only organizations.** Facilities, firms, inputs, and
  programs would each be tempted into a bespoke table. They should be rows
  in a generic entity table with a type, not new tables.

Vertical-by-design tables that are correctly vertical and need no change:
`procurements`, `demand_arc_profiles`, `briefs`/`brief_items`.

## Rule for NEW tables (in force now)

1. If it is a projection/presentation table for one product, vertical
   semantics are acceptable there BUT prefer an open shape (a `tags` array)
   over a fixed domain boolean, so the same table serves a second product
   without a migration.
2. If it is an entity or a relationship, use the generic shape (entity with
   a type; edge with subject/predicate/object plus provenance and
   confidence). Do not add `facilities`, `firms`, or `inputs` tables.
3. If it is a claim, it belongs on the `signals` shape, not a new parallel
   table.

### Applied immediately: `member_live_items`
The live-surface projection table was authored today with a
`defence_relevant boolean` column. That is a vertical semantic on a
structurally generic projection. Because the migration is **not yet
pasted**, changing it is free right now, so it was changed to `tags text[]`
per rule 1. This is better for Signal North on its own merits (the surface
will want grant/category/imminent tags, not just one defence flag) and it
means a second vertical's live surface needs no schema change.
