# Pilot coverage report — the fleet-drain decision artifact

Toronto + Peel, after the operator confirm pass. Run 30270823415, 2026-07-27.
**The fleet drain remains HELD; this is what the decision rests on.**

## What was written
- 33 confirmed procurements, 155 signal links (6 cross-rung threads, ~22 dedups, 4 rhythm groups + R3-cleaned + T37).
- R3 correctness fix applied: signal 751bc4fb re-resolved WRPS→out of Peel.
- 2 dedup merges (Calverley Painting, Eastern Construction — both TPS Facilities) did not re-cluster and were skipped by the structure guard; hygiene only, zero effect on any coverage cell.

## The cells (0g split: only long-lag observations feed significance)

| Fleet class | Service | Transition | confirm_n | **longlag_n** | need for n=8 | median (long-lag) |
|---|---|---|---|---|---|---|
| CLOSE | Peel Regional Police | intent→commitment | 2 | **4** | +4 | 364d, CI[363,385] |
| CLOSE | TPS Board | commitment→awarded | 3 | **3** | +5 | 609d, CI[173,609] |
| CLOSE | Peel Police Board | chatter→intent | 0 | **3** | +5 | 1096d, CI[328,1126] |
| CLOSE | TPS Board | intent→awarded | 0 | **3** | +5 | 155d, CI[155,189] |
| CLOSE | Peel Police Board | intent→commitment | 0 | 1 | +7 | 829d |
| CLOSE | Toronto Police Service | commitment→in_market | 0 | 1 | +7 | 26d |
| CLOSE | Toronto Police Service | in_market→awarded | 0 | 1 | +7 | 282d |
| CLOSE | Toronto Police Service | intent→awarded | 0 | 1 | +7 | 282d |
| CLOSE | Toronto Police Service | commitment→awarded | 0 | 1 | +7 | 308d |
| CLOSE | TPS Board | intent→commitment | 0 | 1 | +7 | 16d |
| CLOSE | Toronto Police Service | intent→commitment | 0 | 1 | +7 | 15d |
| THIN | TPS Board | in_market→awarded | 1 | **0** | +8 | (no long-lag obs) |

**12 cells: 0 PUBLISHED, 11 CLOSE, 1 THIN.** Not one cell is client-publishable today.

## The honest reading (why the CLOSE headline overstates)

The 0g split is the whole story, and it earns its keep here. Take **TPS Board commitment→awarded**: the raw engine calls it **n=6** — tantalizingly close to 8. But the split shows **3 are confirmation pairs** (same-meeting agenda→minutes, 0-day, no predictive value) and only **3 are real long-lag observations**. Without 0g we would have called this cell nearly-significant and been wrong. Same for Peel Regional Police intent→commitment: raw n=6, but only 4 are long-lag.

So the real picture is not "11 cells one drain from significance." It is:
- **4 cells genuinely reachable** (longlag_n 3–4, need +4–5): Peel RP intent→commitment, TPS Board commitment→awarded, Peel Board chatter→intent, TPS Board intent→awarded. A deep drain plausibly gets these to n=8.
- **7 cells at longlag_n=1** (need +7 each): a drain *might* reach them, but each needs 7 more linkable long-lag arcs — a much bigger ask.
- **1 structurally thin.**

Average additional long-lag observations the CLOSE cells need: **6.2 each.**

## The load-bearing finding for the drain decision

Toronto and Peel are the **densest** services in the corpus, and their board history is **already substantially drained** (~$24 of the $63 envelope spent, batches 1–4). Yet the richest cell has only 4 long-lag observations. The binding constraint is **not extraction depth alone** — it is the **structural rarity of linkable long-lag arcs** in board documents: a budget line and its later matching award must BOTH be extracted AND share an instrument the linker can match. Confirmation pairs are cheap and everywhere; sellable long-lag spans are scarce.

**Extrapolation to the fleet:** the other ~25 services are *thinner* than Toronto/Peel, so a fleet drain would yield *fewer* long-lag observations per service, not more. The drain buys **breadth** (more services, more low-n cells) and grows the **4 near cells** toward significance — it does **not** produce a table full of published cells.

## Measured cost, projected to fleet

- Measured drain rate: ~$0.006/doc (mix); board-minutes PDFs (the arc-rich ones) run several times higher.
- Pilot spend so far: ~$24 of the $63 envelope (batches 1–4, ~4,000 docs).
- **Fleet historical drain envelope estimate: ~$135–225** — tier-2 award history (~7,440 docs ≈ $45) plus a deep board-history drain across ~25 services (~15,000–30,000 board PDFs at the higher board rate).

## The judgment you asked for

Does the drain spend buy significance, or risk landing thin per cell? **Both, unevenly.** It buys significance for ~4 specific cells (with real but not certain odds), meaningfully grows Peel RP intent→commitment (n=4, the single most reachable), and adds coverage breadth — but the honest expectation is a table with a *handful* of published cells, not a full one. Reaching a broadly-significant table likely needs the **partial-pooling** estimator (design 0b) to borrow strength across similar services, not drain volume alone.

**Recommendation for your decision (not a go):** approve a *targeted* drain of the 4 near cells' services first (measure whether Peel RP intent→commitment actually crosses n=8), rather than the full ~$135–225 fleet drain — a $20–40 targeted spike answers "does depth convert to significance" before committing the fleet envelope. But this is yours; the drain stays held.
