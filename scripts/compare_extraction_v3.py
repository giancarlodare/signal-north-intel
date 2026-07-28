"""extraction@v2 vs @v3 comparison run (operator-gated prompt-cache change).

v3 restructures the prompt for caching (static instructions in a cached
system block above the 1024-token Opus 4.8 floor; per-doc fields alone in
the user message). The operator's bar: if quality slips AT ALL on the
restructure, it does not ship -- cost savings never justify degrading
extraction. This script runs BOTH versions over the same sample and prints:

  1. per-doc signal diffs (counts; per-signal type/confidence/materiality/
     org/category/amounts/timing/quote presence -- amounts and dates being
     the fields Haiku dropped and Opus was locked in for);
  2. measured cost-per-doc from the real usage counters (input, output,
     cache_write @1.25x, cache_read @0.1x) at Opus 4.8 rates, split by
     title-only vs rich docs.

Sample: title-only tender/award rows (where the cached block dominates
input) plus rich news_release/board_minutes bodies. READ-ONLY: documents
are fetched, nothing is written; document status is untouched. CI only.
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import supabase_client                      # noqa: E402
from src.signal_extractor import DEFAULT_MODEL, extract_signals  # noqa: E402

# Opus 4.8 first-party rates per million tokens.
IN_RATE, OUT_RATE = 5.00, 25.00
CACHE_WRITE_RATE, CACHE_READ_RATE = IN_RATE * 1.25, IN_RATE * 0.10

SAMPLE = [
    # (doc_type, n, label) -- title-only rows first, then rich bodies.
    ("tender_notice", 6, "title-only"),
    ("award_notice", 4, "title-only"),
    ("news_release", 3, "rich"),
    ("board_minutes", 3, "rich"),
]


def fetch_sample():
    docs = []
    for doc_type, n, label in SAMPLE:
        rows = supabase_client.fetch_rows_where(
            "documents",
            "id,source_id,title,doc_type,published_on,url,content",
            {"doc_type": f"eq.{doc_type}"}, limit=n * 3)
        rows.sort(key=lambda r: str(r.get("published_on") or ""), reverse=True)
        if label == "rich":
            rows = [r for r in rows if len(r.get("content") or "") > 2000]
        picked = rows[:n]
        for r in picked:
            r["_label"] = label
        docs.extend(picked)
        print(f"  sampled {len(picked)} {doc_type} ({label})")
    return docs


def cost_usd(u: dict) -> float:
    return (u.get("input_tokens", 0) * IN_RATE
            + u.get("output_tokens", 0) * OUT_RATE
            + u.get("cache_write_tokens", 0) * CACHE_WRITE_RATE
            + u.get("cache_read_tokens", 0) * CACHE_READ_RATE) / 1e6


def sig_key(s: dict) -> tuple:
    return (s.get("signal_type"), (s.get("title") or "")[:40].lower())


def summarize(sig: dict) -> str:
    amt = sig.get("amount_min_cad")
    return (f"{sig.get('signal_type')}/{sig.get('confidence')}"
            f"/m{sig.get('materiality')}"
            f" org={ (sig.get('organization_name') or '-')[:28]!r}"
            f" cat={sig.get('category_slug') or '-'}"
            f" amt={amt if amt is not None else '-'}"
            f" timing={(sig.get('expected_timing') or '-')[:20]!r}"
            f" quote={'Y' if sig.get('quote_or_line') else 'N'}")


def field_counts(signals: list) -> Counter:
    c: Counter = Counter()
    for s in signals:
        c["signals"] += 1
        c["with_org"] += 1 if s.get("organization_name") else 0
        c["with_category"] += 1 if s.get("category_slug") else 0
        c["with_amount"] += 1 if s.get("amount_min_cad") is not None else 0
        c["with_timing"] += 1 if s.get("expected_timing") else 0
        c["with_quote"] += 1 if s.get("quote_or_line") else 0
        c[f"conf_{s.get('confidence')}"] += 1
        c[f"mat_{s.get('materiality')}"] += 1
    return c


def main() -> int:
    model = DEFAULT_MODEL
    print(f"model: {model}")
    print("sampling documents (read-only)...")
    docs = fetch_sample()
    src_names = {}

    results = {}
    for version in (2, 3):
        usage_by_label = {"title-only": {}, "rich": {}}
        per_doc = []
        for doc in docs:
            sid = doc["source_id"]
            if sid not in src_names:
                src_names[sid] = supabase_client.get_source_name(sid)
            u: dict = {}
            signals, stamp = extract_signals(doc, src_names[sid], model,
                                             usage_totals=u,
                                             prompt_version=version)
            for k, v in u.items():
                bucket = usage_by_label[doc["_label"]]
                bucket[k] = bucket.get(k, 0) + v
            per_doc.append({"doc": doc, "signals": signals, "usage": u})
        results[version] = {"per_doc": per_doc, "usage": usage_by_label,
                            "stamp": stamp}

    # ---- quality diff --------------------------------------------------
    print("\n" + "=" * 74)
    print("QUALITY DIFF (v2 vs v3, same documents)")
    agg = {2: Counter(), 3: Counter()}
    flips = 0
    for d2, d3 in zip(results[2]["per_doc"], results[3]["per_doc"]):
        doc = d2["doc"]
        s2, s3 = d2["signals"], d3["signals"]
        agg[2] += field_counts(s2)
        agg[3] += field_counts(s3)
        same = len(s2) == len(s3) and (
            {sig_key(s) for s in s2} == {sig_key(s) for s in s3})
        marker = "==" if same else "!!"
        if not same:
            flips += 1
        print(f"\n{marker} [{doc['_label']}] {doc['doc_type']} :: "
              f"{(doc.get('title') or '')[:64]}")
        print(f"   v2: {len(s2)} signal(s)")
        for s in s2:
            print(f"      {summarize(s)}")
        print(f"   v3: {len(s3)} signal(s)")
        for s in s3:
            print(f"      {summarize(s)}")

    print("\n" + "=" * 74)
    print(f"AGGREGATE (docs={len(docs)}, docs_with_signal_set_changes={flips})")
    keys = sorted(set(agg[2]) | set(agg[3]))
    print(f"  {'field':22s} {'v2':>6s} {'v3':>6s}")
    for k in keys:
        print(f"  {k:22s} {agg[2].get(k, 0):>6d} {agg[3].get(k, 0):>6d}")

    # ---- cost ----------------------------------------------------------
    print("\n" + "=" * 74)
    print("COST PER DOC (measured usage, Opus 4.8 first-party rates)")
    n_by_label = Counter(d["_label"] for d in docs)
    for version in (2, 3):
        print(f"\n  extraction@v{version}:")
        total = 0.0
        for label, u in results[version]["usage"].items():
            n = n_by_label[label] or 1
            c = cost_usd(u)
            total += c
            print(f"    {label:11s} docs={n}  input={u.get('input_tokens', 0)}"
                  f" out={u.get('output_tokens', 0)}"
                  f" cache_write={u.get('cache_write_tokens', 0)}"
                  f" cache_read={u.get('cache_read_tokens', 0)}"
                  f"  cost=${c:.4f} (${c / n:.4f}/doc)")
        print(f"    TOTAL ${total:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
