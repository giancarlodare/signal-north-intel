# Near-cell drain experiment — does depth convert to significance?

Targeted drain of the 4 near-cell services, 2026-07-27. ~$3–6 measured (171
board docs extracted, 635 new signals, ~$0.02–0.04/board-PDF).

## The success test you named: NO on both counts

**Peel RP intent→commitment — the flagship cell — did not move.**

| | before drain | after drain (+635 signals) |
|---|---|---|
| longlag_n | 4 | **4 (unchanged)** |
| median | 364d | **364d (unchanged)** |
| CI | [363, 385] | **[363, 385] (unchanged)** |

It did not cross n=8. Its CI did not tighten. It is byte-for-byte identical after extracting 171 new board documents into the densest service's densest cell.

## What the depth *did* buy (breadth, not the key cell)

The corpus grew 12→14 cells, and a few cells gained observations:
- TPS Board intent→commitment: longlag_n 1→3
- TPS Board intent→awarded: median shifted 155→744d (different observations)
- Toronto Police Service commitment→in_market (n=2) and commitment→awarded (n=2) appeared/grew
- 2 brand-new Peel RP cells appeared, but at longlag_n=1 with absurd medians (commitment→awarded = **2832 days / 7.7 years**, intent→awarded = 1769d) — single stray observations, not signal.

Still **0 PUBLISHED cells**, still 1 THIN, average +6.0 long-lag observations needed per CLOSE cell.

## The honest verdict

**Depth does not convert to significance on the best cell.** Pouring 635 fresh signals into the densest service produced zero growth in the flagship predictive cell, and pushed no cell to n=8. This confirms the coverage report's thesis directly: the binding constraint is the **structural rarity of linkable long-lag arcs**, not extraction depth. A long-lag observation needs a dated budget-intent AND its later dated commitment for the *same* procurement, both extracted and linked — that specific structure is rare in board minutes, and adding more minutes doesn't manufacture it.

**This is the fork you set: it did not convert, so the route is the partial-pooling estimator (0b), not drain volume.** The full fleet drain (~$135–225) would buy the same thing this $3–6 experiment bought at the flagship cell: breadth and noise, not per-cell significance. Do not spend it for significance.

## One caveat I owe you (the experiment's boundary)

The confirm-pass writer links a **fixed** confirmed-cluster list, so it captures new signals only where they fall *into* an already-confirmed cluster. It cannot see brand-new arcs the drain may have surfaced (a new Peel RP intent→commitment thread that wasn't in your confirmed set). To make the negative result airtight, the definitive test would re-run the **proposer staging** on the post-drain corpus and bring you any newly-surfaced Peel RP arcs to confirm — that closes the "did depth surface new confirmable arcs" question the fixed writer can't.

My read: even accounting for that, the signal is strong enough to act on. The flagship cell is a *rhythm* group that already links all its Peel RP domain signals, so new intent/commitment pairs in that domain would have grown it — and it didn't grow. Depth into the confirmed structure is exhausted as a significance lever.

## Recommendation (your call)

1. **Do NOT approve the fleet drain for significance.** It is confirmed it won't deliver.
2. **Stand up partial pooling (0b)** as the real route to a broadly-significant table — the empirical-Bayes path, days not weeks, costed in the design doc.
3. **Optional, cheap:** one proposer re-run on the post-drain corpus to confirm no new Peel RP arcs were surfaced, if you want the negative result fully airtight before committing to pooling.
4. Independently worthwhile regardless: the **board-minutes-ahead-of-awards** cadence reprioritization (task #52) — board history is prediction fuel and it's being starved; that helps breadth and future pooling groups even though it won't make the flagship cell significant.
