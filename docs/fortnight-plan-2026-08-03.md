# Fortnight plan: full scope by Aug 16 (operator 2026-08-02, evening)

Nothing gets cut. Grant writer Aug 17-30. The four process changes that
make the schedule feasible are binding and recorded in the decision log:

1. **Safe class widens to collect-only work.** New collectors touching no
   schema, no member-facing surface and no LLM spend are build-and-report.
   Robots posture checked and reported, validation table produced,
   boundaries named. Design-first stays for schema / member-facing /
   spend / public claims. Unsure = gated.
2. **One standing August extraction envelope** (proposal below). Approved
   once; the guard enforces batch by batch and surfaces only if a batch
   would exceed the total.
3. **Gated items queue into two windows a day** (morning and evening
   Eastern). Genuinely blocking items are marked in the queue for
   pull-forward.
4. **Batch-validation harness extends to every new source.** One table per
   wave: host, docs, parse rates, coverage. Table approved; below-bar rows
   flagged, never blocking.

## Standing August envelope: $600 proposed

| component | basis | projection |
|---|---|---|
| Board backlog (61 eScribe + 5 CivicWeb, historical) | ~66 tenants x ~150 backlog docs (fleet-discovery sample: 2-3 docs/meeting) at ~$0.03/doc (board PDFs run longer than the $0.019 Peel portal rate) | ~$300 |
| Council agendas wave 1 (32 career-dept municipalities + big cities, current year) | ~1,200 docs at $0.03 | ~$40 |
| Fire / EMS / defence expansion (OFM, Metrolinx, Ontario Newsroom, new collectors, light backlog) | ~3,000 docs at $0.02-0.03 | ~$75 |
| Demand-voice classification | already-approved classifier band | $50 |
| Labour lens (OPAAC awards extraction; Sunshine is CSV, no LLM) | ~500 docs at $0.03 | $15 |
| Relevance calibration + full backfill | approved band | $15 |
| Contingency (rates are projections; the guard binds) | ~17% | $105 |
| **Total** | | **$600** |

Mechanics: every batch still measures its own seed rate before dispatch;
the guard debits the standing envelope and SKIPs (green, surfaced) any
batch that would cross the remaining balance, exactly as today, but the
surfacing goes to the queue, not a fresh approval round-trip. Unspent
balance simply is not spent. Steady-state daily forward pass, weekly
discovery and monthly calibration stay outside, as before.

## Day-by-day (Aug 3-16)

| day | lands | operator on critical path |
|---|---|---|
| Aug 3 | eScribe adapter built; first-wave tenants validated (Ottawa, Niagara, London, Hamilton + bucket-A set); enumeration completed (deep-crawl + OAPSB/OACP ingest) | **Tonight/AM: standing envelope approval; relevance migration paste** (blocks the whole scorer thread) |
| Aug 4 | Seeding wave 1 (~15 tenants) + validation table 1; CivicWeb adapter + its 5 hosts | AM window: table 1. **All remaining schema pastes batched into ONE paste set** (closes_on column, anything categorization needs) so no later day blocks on SQL |
| Aug 5 | Seeding waves 2-3 (~30 tenants) + table 2; calibration batch (200) + same-cycle side-by-side at floors 3 and 4 | **PM window: lens ruling** (threshold + window widening) — gates the scorer |
| Aug 6 | Remaining tenants + straggler table; council-agenda extension (committee-first) collecting; board backlog drain batch 1 under the envelope | AM window: table 3 |
| Aug 7 | Scorer behind fixture tests (post-ruling); relevance full backfill; categorization: notice_kind, buyer typing (PSPC worked example) | — |
| Aug 8 | Composed arc body field (Weekly item 1); cluster/merge improvements; fire/EMS/defence collectors wave (GO'd list) | — |
| Aug 9 | Weekly send half (#57, double opt-in as ruled) staged dark | **SMTP domain DNS (SPF/DKIM/DMARC) — front-loaded here at the latest; propagation takes days, so sooner is safer** |
| Aug 10 | Issue archive (Weekly item 3); shadow lens cycle 1 report | PM window: shadow report |
| Aug 11 | Demand-voice collectors (coroner, AG, OCPC, IoP, associations x4, trade press) AFTER the Annex robots/terms assessment reports; asker weights | AM window: Annex verdict + any boundary calls |
| Aug 12 | Labour lens collection (OPAAC awards, Sunshine #138 apply after validation); vendor rosters (CADSI, OACP-B2B, OAFC industry; company-level only) | — |
| Aug 13 | Precedent matching; closes_on extraction (column pasted Aug 4); generated-types CI | — |
| Aug 14 | Silent-failure audit sweep; shadow cycle 2; coverage page built from the scoped table | **PM window: coverage page copy ruling** (public claim) |
| Aug 15 | Hardening buffer; consolidated validation tables; member-facing staging pass | AM window: staging review |
| Aug 16 | Landing day: final validation, coverage regeneration, launch checklist | Final go |

## The five approvals that are genuinely on the critical path

1. Standing envelope (tonight) — blocks every backlog drain.
2. Relevance migration paste (tonight/tomorrow AM) — blocks calibration,
   side-by-side, scorer, backfill.
3. Lens ruling from the side-by-side (Aug 5 PM) — blocks the scorer build.
4. SMTP DNS records (by Aug 9, earlier is safer) — blocks the send half.
5. Coverage page copy (Aug 14 PM) — blocks the page shipping.

Everything else queues into the two daily windows as tables and reports.
