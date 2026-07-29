"""Count the remaining extraction backlog, so an ENVELOPE can be declared
from a measured doc count rather than a guess (operator, cost discipline,
2026-07-28). Read-only, no LLM, no writes.

Reports captured (unextracted) documents by doc_type and by url host, plus
the tier-3 remainder specifically, so the unscoped drain's remaining work
can be priced at the measured per-doc rate before the next batch runs.
"""
import os
import sys
from collections import Counter
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import supabase_client as sc  # noqa: E402

TIER3 = ("stcatharines.bidsandtenders.ca", "thunderbay.bidsandtenders.ca",
         "whitby.bidsandtenders.ca", "burlington.bidsandtenders.ca")
# The unscoped drain's own doc-type scope, from extract-backfill.yml.
DRAIN_TYPES = ("award_notice", "board_minutes", "news_release")
# Buyers HELD from the drain by the standing cost gate.
EXCLUDED_BUYERS = ("City of Hamilton", "City of Brampton", "City of Kitchener",
                   "City of Vaughan", "Halton Region")

rows = sc.fetch_all_rows_where(
    "documents", "id,doc_type,url,buyer_name", {"status": "eq.captured"})
print(f"captured (unextracted) documents: {len(rows)}")

by_type = Counter(r.get("doc_type") or "(none)" for r in rows)
print("\nby doc_type:")
for t, n in by_type.most_common():
    print(f"  {t:20s} {n:6d}")

drain = [r for r in rows
         if (r.get("doc_type") in DRAIN_TYPES)
         and (r.get("buyer_name") not in EXCLUDED_BUYERS)]
print(f"\nIN SCOPE for the unscoped drain "
      f"(doc_type in {DRAIN_TYPES}, held buyers excluded): {len(drain)}")

by_host = Counter(urlparse(r.get("url") or "").netloc or "(none)" for r in drain)
print("\n  by host (drain-eligible only):")
for h, n in by_host.most_common(20):
    mark = "  <-- TIER-3" if h in TIER3 else ""
    print(f"    {h:45s} {n:6d}{mark}")

t3 = sum(n for h, n in by_host.items() if h in TIER3)
print(f"\nTIER-3 remainder still captured: {t3}")

RATE = 0.0194  # measured this session: batch1 $19.37/1000, batch2 $19.16/1000
print(f"\nENVELOPE INPUT: {len(drain)} drain-eligible docs "
      f"x ${RATE:.4f}/doc (measured) = ${len(drain) * RATE:,.2f}")
print(f"  tier-3 portion of that: {t3} x ${RATE:.4f} = ${t3 * RATE:,.2f}")
print(f"  non-tier-3 remainder:   {len(drain) - t3} docs = "
      f"${(len(drain) - t3) * RATE:,.2f}")
