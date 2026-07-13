# Legal Seam: Investor-Facing Product (for counsel)

**Status: FLAGS FOR REVIEW, not legal advice.** This document exists so that
counsel can review the investor-facing seam before any investor-facing output
is built. Per operator instruction, the investor line is a Phase 2 product
pending legal review. Nothing investor-facing is being built now. The seller
product (companies assessing their own procurement odds) is the day-one
product and carries materially lower risk than the investor line on every
point below.

The purpose here is to point out where the prediction and track-record design,
when aimed at investors, could raise securities, insider-information, or
market-manipulation questions, so they can be put to counsel deliberately
rather than discovered later.

## Context counsel needs

- **Inputs are strictly public.** Every signal and every prediction rests on
  publisher-URL documents already in the corpus, enforced structurally
  (a prediction cannot exist without a linked public evidence document). There
  is no private or purchased data feed, and no social-media ingestion.
- **A standing firewall already exists.** The operator holds a government role.
  A standing rule bars anything learned in an official capacity from entering
  the system. The prediction ledger inherits this structurally: claims can
  rest only on public record.
- **Claims are immutable and time-stamped.** Each prediction is frozen at
  creation with an authoritative timestamp and a tamper-evident hash. The
  track record is auditable, not editable after the fact.
- **Canadian-hosted.** All data lives in a Canadian-region database. No
  investor delivery mechanism has been built; any future one gets its own
  data-residency review.

## The flags

### 1. Adviser or research registration
Selling forward-looking predictions about publicly traded issuers to funds may
constitute investment research or adviser activity under provincial securities
law (the CSA framework, for example the OSC in Ontario). The seller product,
which tells a company about its own procurement odds, is a different activity
and is far less likely to implicate registration. **Question for counsel:**
does an investor-facing prediction or track-record product require
registration, and if so in which category.

### 2. Performance representation
Marketing a hit-rate to investors is a performance claim. Performance
representations are subject to advertising rules for registrants and to general
misrepresentation liability. The same hit-rate shown to a seller about
government procurement is not a securities performance claim. **Question for
counsel:** how a track-record or hit-rate may be presented to investors, and
what substantiation and disclaimers are required.

### 3. Material non-public information and tipping
"Before the market sees it" is the core value proposition and is precisely the
shape regulators scrutinize. The intended defence is that every input is public
record, timestamped and auditable, and the prediction is synthesis of public
data rather than any private fact. **Questions for counsel:** whether synthesis
of public information can nonetheless be treated as MNPI when sold selectively
to investors; and whether selling a specific "Company X will win Procurement Y"
call to a fund before the outcome is public constitutes tipping. The immutable,
public-provenance design is meant to support the defence, but the question
should be settled before any investor output ships.

### 4. Market manipulation and proprietary positions
Predictions on thinly traded issuers could move them. **Recommendation to put
to counsel:** a policy of no proprietary positions in covered issuers, and no
investor product paired with any trading by the operator or the company, agreed
before Phase 2. This is a governance decision, not only a legal one.

### 5. Selective disclosure and timing fairness
If the same prediction reached a fund earlier or on better terms than it
reached sellers, the timing asymmetry could be attacked. The design mitigates
this with a single authoritative timestamp per immutable claim, with every
audience view reading that same frozen claim rather than a re-timed copy.
**Question for counsel:** whether differential access to the same timestamped
claim across audiences raises fairness or selective-disclosure concerns.

### 6. Privacy of decision-makers
The seller output includes "who decides." **Design rule, for confirmation:**
this stays public official roles and titles, not personal data about
individuals, to keep clear of PIPEDA. **Question for counsel:** confirm that
naming public office-holders in their official procurement roles is acceptable,
and where the line sits.

## What the design already does to reduce exposure

- Public-only provenance, enforced by a NOT NULL evidence link on every claim.
- The government-capacity firewall, inherited structurally by the ledger.
- Immutable, timestamped, tamper-evident claims for a clean audit trail.
- An audience-neutral engine with audience isolated to an export layer, so the
  investor path can be gated, reviewed, and turned off at a single seam.
- Canadian data residency preserved end to end.

## What is deliberately not built pending review

- No investor-facing export, page, route, or delivery mechanism.
- No pairing of predictions with any trading activity.
- No differential timing of a claim across audiences.

The investor export exists in the design only as a dark, gated stub with a
documented schema, so that its shape can be reviewed here before it is ever
turned on.
