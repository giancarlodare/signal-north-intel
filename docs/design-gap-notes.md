# Design-gap notes: Claude Design handoff vs CC-rendered pages

Working log for closing the gap between the Claude Design handoff
(`web/design-handoff/`) and the Next.js render. Root cause established
2026-07-28: the tokens, marketing CSS, and dashboard CSS all ported VERBATIM
and the webfonts load; there is no Tailwind (it is hand-written CSS +
custom properties, matching the handoff). Drift, where it exists, is in the
page MARKUP, not the stylesheet. Method: check each page's inline blocks
against its handoff HTML source before converting, so we distinguish
scale-centralization (render-identical) from a real visible fix.

## Standing conversion rule (operator 2026-07-28)

For dashboard/member pages: convert inline heading styles to the
design-system's own classes (.t-title, .t-heading, .t-label) where they map,
and to --fs-*/--sp-* token variables where a number is an exact token match.
Where the handoff ITSELF uses an off-scale value, KEEP the literal
pixel-matched to the target and flag it in a code comment; do not snap it
(snapping would make the render diverge from the approval target).

## Upstream design questions (operator's call in Claude Design, not render fixes)

### Handoff type-scale reconciliation (my call later -- operator 2026-07-28)
The handoff uses some values that fall off its OWN published type scale:
  * hero headline 44px  (this one IS on scale: --fs-title = 44)
  * item heading 25px   (nearest token --fs-subhead = 24)
  * item note 14px      (between --fs-small 13 and --fs-ui 15)
  * editor label 10px   (label token = 11)
  * hero bottom pad 56px, hero gap 14px (off the 8px grid)
Whether these should be reconciled onto the type scale is an UPSTREAM design
decision the operator will make in Claude Design, then re-port. Until then
the render matches the current handoff exactly. NOT a render-side fix.

## Brief page (dashboard) -- converted 2026-07-28

* Hero headline -> .t-title (+ white color override for the navy hero).
* Lead item heading -> .t-heading. Exact gaps/padding edges -> --sp-* tokens.
  Editor note body -> --fs-ui. Item count -> --fs-small.
* Render-identical to the handoff (the handoff inlined these; this is
  scale-centralization, not a visible fix).
* Five off-scale values LEFT pixel-matched to the handoff with flag comments
  (operator decision 2026-07-28: match the target; scale purity is an
  upstream Claude Design decision, see above): item heading 25px, item note
  14px, editor label 10px, hero pad 56px, hero gap 14px.

### Brief data-model decisions -- to resolve when composing the first issue
These are the REAL differences between our brief and the target, and they
are CONTENT/data decisions, not style. Parked for the editorial cycle
(operator 2026-07-28: "the same question as what a brief item contains,
which I'll feel when I compose the first brief"). DO NOT build fields
speculatively.
  1. Per-item narrative BODY paragraph (handoff renders a 2-3 sentence body
     at 17px). We have no backing field; today we render the editor note +
     provenance instead.
  2. Distinct week-story HERO line vs the lead item's headline. The handoff
     hero carries a week-story sentence; ours reuses the lead headline, so
     the lead appears to repeat in hero + lead h3.
  3. Issue NUMBER ("No. 31"). No backing field; omitted today.
Resolve all three together when the first issue is composed: they answer one
question -- what does a brief item contain.

## Home page (dashboard) -- converted 2026-07-28
VERDICT: CENTRALIZATION (already faithful, like the brief). The home page
already used the handoff's heading classes (.dash-hero__title, .brief-panel,
.flag-card__match, .t-label), and its inline blocks are LAYOUT values
(gap/padding/flex) that match the handoff index.html's own inline values.
Converted the exact-match layout gaps/padding and the exact font-sizes to
--sp-*/--fs-* tokens; render-identical. Four off-scale values, all present
in the handoff index.html, LEFT pixel-matched with flag comments per the
standing rule: watch-summary 14px, activity-log column gap 14px, saved-card
gap 5px, activity-row text 13.5px. No visible drift-fix; scale-centralization
only.

## Closing-soon page (dashboard) -- converted 2026-07-28
VERDICT: CENTRALIZATION (authored-to-convention). No handoff HTML exists
(this is the new live surface), so it was checked against the design-system
conventions the brief and home establish. It already used the design-system
classes (dash-hero__title, flag-card, flag-card__meta, mono-meta, src-link);
all five inline numbers mapped to EXACT tokens (gap 16/8/20 -> --sp-4/2/5,
fontSize 13 -> --fs-small) with ZERO off-scale values -- cleaner than the
ported pages, which is the payoff of authoring to convention. Converted all
five; render-identical; no flags needed.

## Marketing pages (home, about, pricing) -- operator-driven, worst-first
Narrower structural mismatches; the operator will point at each with paired
screenshots. Pricing page pass ALSO folds in the honest live-vs-in-
development tier-table marker (wording to operator for approval at that
time; see docs/tiered-product-map.md).
