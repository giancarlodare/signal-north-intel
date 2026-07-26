# Tier-2 bids&tenders enablement record

Status: PROVENANCE COMPLETE, 9 of 9 including the optional Halton Hills
row (2026-07-21, sprint front 4; Vaughan and Halton Region passed by
operator browser, the rest by machine crawl). Enablement is
gated on the Sunday Jul 26-27 brief drafting correctly from the current
cohort; the wave enables Monday Jul 28 on the operator's go. Every
enabled row is a MUNICIPALITIES config entry in
src/tenders_bidsandtenders.py plus a URL-guarded sources row and an
ORG_SEED entry, validated by the standard CI dry-run before merge.

## Provenance table (the gate each row passed)

| Buyer | Tenant | Provenance evidence | Verdict |
|---|---|---|---|
| City of Hamilton | hamilton.bidsandtenders.ca | hamilton.ca/build-invest-grow/buying-selling-city/bids-and-tenders links the tenant (CI probe job 88636980088) | PASS |
| City of Brampton | brampton.bidsandtenders.ca | brampton.ca homepage plus four Doing-Business pages link the tenant (same probe) | PASS |
| City of Markham | markham.bidsandtenders.ca | markham.ca/economic-development-business/bids-tenders links the tenant (same probe) | PASS |
| City of Mississauga | mississauga.bidsandtenders.ca | mississauga.ca .../doing-business-with-the-city/bid-opportunities/ links the tenant (round-2 sitemap probe, job 88638891712) | PASS |
| City of Kitchener | kitchener.bidsandtenders.ca | kitchener.ca/business-in-kitchener/procurement/ links the tenant (round-2 probe) | PASS |
| Niagara Region | niagararegion.bidsandtenders.ca | niagararegion.ca/business/tenders/default.aspx links the tenant (round-3 probe, job 88639498421) | PASS |
| City of Vaughan | vaughan.bidsandtenders.ca | OPERATOR BROWSER 2026-07-21 (vaughan.ca 403s the collector UA): vaughan.ca/business/procurement-services states "The City of Vaughan uses bids&tenders" and links the tenant twice | PASS |
| Halton Region | haltonregion.bidsandtenders.ca | OPERATOR BROWSER 2026-07-21: halton.ca/the-region/finance-and-transparency/doing-business-with-the-region states bid opportunities are on "Halton's Bid Opportunities website, Bids and Tenders" with a direct tenant link. This also settles the two-channel question: bids&tenders is the PUBLISHER-NAMED channel; merx.com/haltonregion is secondary and NOT a collector target | PASS |
| Town of Halton Hills | haltonhills.bidsandtenders.ca | haltonhills.ca/work/bids-tenders links the tenant (CI probe job 88649903849, same day). The optional ninth's condition is met | PASS |

Corrected probe artifact: the earlier tier survey used the wrong region
slugs; halton.bidsandtenders.ca and niagara.bidsandtenders.ca error out,
haltonregion and niagararegion are the real tenants.

## MERX confirmed buyers (separate wave, provenance pending per buyer)

merx.com/cityofwindsor, merx.com/cityofgreatersudbury, and
merx.com/haltonregion exist and are public (CI probe job 88636980088).
Each needs its own publisher-linked provenance check before a sources row;
Windsor's MERX page is secondary to the already-live open-data collector,
and Halton's is RECORDED SECONDARY (halton.ca names bids&tenders as its
channel; see the table). Sudbury remains the live MERX candidate. All
other tier-2 slug guesses 404 (London, Hamilton, Peel, York, Durham,
Waterloo, and city-name variants).

## Tier-2 wave GO + first-multi-buyer-week watch flags (operator 2026-07-26)

The Sunday Jul 26 brief gate PASSED: machinery correct (dates, provenance,
lens, honest exclusion accounting); the brief's thinness was diagnostic of
single-buyer concentration (the lens correctly held 21 already-featured Peel
items), which this wave fixes. The nine buyers enable Monday Jul 28.

WATCH FLAGS for the first multi-buyer week, both checked at the next Sunday
gate (Aug 2):

1. **Brief thickness**: with tier-2 buyers feeding the lens fresh material,
   next week's brief should be MATERIALLY thicker. Still-thin after tier-2
   is a real editorial problem to diagnose, not a quiet week.
2. **Lens scaling**: the previously-featured lens did its job but starved
   the brief under one dominant buyer. Confirm the lens logic scales
   sensibly across many buyers in the first multi-buyer week (per-item
   keys, no cross-buyer suppression surprises).

## Tier-2 CI validation verdict (run 30211978378, 2026-07-26): 5 enable, 4 held

Standard bars (reference parse, date parse, awarded check), Chromium
dry-run across all 14 config rows; tier-1 all healthy in the same run.

| Buyer | open rows | ref parsed | date parsed | awarded rows | Verdict |
|---|---|---|---|---|---|
| City of Hamilton | 7 | 100% | 100% | 1,374 | ENABLE |
| City of Brampton | 10 | 100% | 100% | 1,674 | ENABLE |
| City of Kitchener | 6 | 100% | 100% | 1,299 | ENABLE |
| City of Vaughan | 12 | 100% | 100% | 1,715 | ENABLE |
| Halton Region | 17 | 100% | 100% | 1,377 | ENABLE |
| City of Markham | 0 | n/a | n/a | 0 | HELD: dead OPEN grid |
| Niagara Region | 0 | n/a | n/a | 0 | HELD: dead OPEN grid |
| Town of Halton Hills | 0 of 29 rendered | n/a | n/a | 0 | HELD: markup variant (grid rendered, parser missed; most fixable) |
| City of Mississauga | 1 | 100% | 100% | 0 | HELD: awarded replay empty (endpoint variant) |

Diagnose-and-extend applies to the four holds: each needs its own probe
(markup variant for Halton Hills, tenant/gating check for Markham and
Niagara, awarded-endpoint variant for Mississauga) before a follow-up
enable PR. Their provenance stands; only collectability is open.

## Tier-3 batch: operator-browser provenance (2026-07-26), QUEUED

Provenance established by OPERATOR BROWSER 2026-07-26: each city's
official procurement page links its bidsandtenders tenant. The
globaltenders.com links seen alongside are AGGREGATORS and are ignored
as sources, per the standing provenance rule. Machine candidates had
404'd on stale page paths (the go-batch sweep); the operator's browser
found the moved pages.

QUEUE DISCIPLINE (operator instruction): these do NOT displace the
proposer confirm pass (pilot critical path) or the Monday tier-2 wave.
They run through the standard CI validation dry-run (reference parse /
date parse / awarded check, tier-1 bars) when those two clear, then
enable on the operator's go.

| Buyer | Tenant | Provenance evidence | Verdict |
|---|---|---|---|
| City of Niagara Falls | niagarafalls.bidsandtenders.ca | niagarafalls.ca/building-planning-and-business/procurement-services/bid-opportunities/ links the tenant | PASS (operator browser) |
| City of St. Catharines | stcatharines.bidsandtenders.ca | stcatharines.ca/business-and-economic-development/vendor-and-purchasing-opportunities/ links the tenant | PASS (operator browser) |
| City of Thunder Bay | thunderbay.bidsandtenders.ca | thunderbay.ca/en/business/tenders-and-proposals.aspx links the tenant | PASS (operator browser) |
| Town of Whitby | whitby.bidsandtenders.ca | whitby.ca/business-and-economy/bid-opportunities/ links the tenant | PASS (operator browser) |
| City of Burlington | burlington.bidsandtenders.ca | burlington.ca/en/business-in-burlington/bid-opportunities.aspx links the tenant | PASS (operator browser) |
| City of Sarnia | sarnia.bidsandtenders.ca | sarnia.ca/working-here/bids-and-tenders/ links the tenant | PASS (operator browser) |
| City of London | london.bidsandtenders.ca | london.ca/business-development/procurement-supply links the tenant | PASS (operator browser) |

Already covered by the Monday tier-2 wave (no new rows needed):
Hamilton and Mississauga passed provenance 2026-07-21 and sit in the
tier-2 table above. CAVEAT carried to validation time: the go-batch
sweep saw a robots/500 shape on a Hamilton endpoint; confirm
hamilton.bidsandtenders.ca itself is collectable (robots + probe)
before its row enables.

HIGH-VALUE PROBE, QUEUED: London Police Service has its OWN bids page,
londonpolice.ca/about/bids-and-tenders/ (operator find, 2026-07-26). A
police-service-direct procurement channel outranks a city feed for the
niche. Probe when the queue clears: platform identification,
collectability (robots, rendering), provenance confirmation, then
design-first if collectable.
