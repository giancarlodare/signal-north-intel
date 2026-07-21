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
