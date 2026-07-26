"""Upstream-intent layer, Wave A: the corpus intent pass
(docs/upstream-intent-scale-design.md; classifier proven in the two Peel
precision rounds, realized-acquisition sense included).

Runs the strict intent classifier over ALREADY-COLLECTED board_minutes
documents of the live boards: zero new collection, immediate demand-arc fuel.
Dry-run (the default) prints the per-board VALIDATION line and every non-noise
classification with evidence, so the wave's bar (precision spot-check per
board, leak-check) is adjudicated before any signal writes.

    python -m src.upstream_intent --dry-run --per-board 8
"""
import argparse
import json
import logging
import os
import sys
from collections import Counter, defaultdict

from . import supabase_client

log = logging.getLogger(__name__)

MODEL = os.environ.get("EXTRACTION_MODEL", "claude-opus-4-8")
MAX_BODY = 6000

# Live boards -> the url substring their corpus documents carry (from the
# board_minutes BOARDS config). Config-tunable; adding a board is a row.
BOARDS = [
    ("Toronto Police Service Board", "tpsb.ca"),
    ("Peel Police Services Board", "peelpoliceboard.ca"),
    ("York Regional Police Services Board", "yrpsb.ca"),
    ("Durham Regional Police Services Board", "durhampoliceboard.ca"),
    ("Halton Police Board", "haltonpoliceboard.ca"),
    ("Waterloo Regional Police Services Board", "wrps"),
    ("Greater Sudbury Police Services Board", "gsps.ca"),
]

_SYSTEM = (
    "You are a strict procurement-intelligence classifier for a police "
    "service's public documents. Your job is signal-vs-noise: most content is "
    "noise (ceremonies, HR, community events, routine reporting). A fraction "
    "genuinely telegraphs future buying or funding a vendor could act on. "
    "Classify each document into exactly one label:\n"
    "- procurement_intent: the service signals acquiring goods/services/"
    "technology/vehicles/facilities. BOTH senses: FUTURE intent (planning, "
    "pilot, upcoming RFP, capital/facility plan) AND REALIZED acquisition "
    "(introduces / deploys / launches / adopts / rolls out / implements a "
    "tool, system, technology, or service; a realized deployment confirms the "
    "buy and implies follow-on and expansion).\n"
    "- funding_intent: seeking or receiving funding, a grant, or a budget "
    "(operating or capital) that implies future buying.\n"
    "- pressure_signal: a demand-pressure indicator (crime trend, capacity "
    "strain, rising incident category) that raises the likelihood of future "
    "buying but names no purchase.\n"
    "- noise: everything else.\n"
    "Be conservative: default to noise unless there is a CONCRETE signal. "
    "Precision matters more than recall. Put the exact triggering phrase in "
    "'evidence' (empty for noise)."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string",
                  "enum": ["procurement_intent", "funding_intent",
                           "pressure_signal", "noise"]},
        "confidence": {"type": "number"},
        "rationale": {"type": "string"},
        "evidence": {"type": "string"},
    },
    "required": ["label", "confidence", "rationale", "evidence"],
    "additionalProperties": False,
}


def classify(client, title: str, body: str) -> dict:
    prompt = f"DOCUMENT TITLE: {title}\n\nDOCUMENT BODY:\n{body[:MAX_BODY]}\n\nClassify this document."
    resp = client.messages.create(
        model=MODEL, max_tokens=512, system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return json.loads(text)


def board_docs(url_marker: str, n: int) -> list:
    rows = supabase_client.fetch_rows_where(
        "documents", "id,title,url,content,published_on",
        {"doc_type": "eq.board_minutes", "url": f"ilike.*{url_marker}*",
         "content": "not.is.null"},
        limit=n * 3)
    rows.sort(key=lambda r: str(r.get("published_on") or ""), reverse=True)
    return [r for r in rows if (r.get("content") or "").strip()][:n]


# Wave A label -> honest taxonomy signal_type (grades via src/taxonomy.py):
# board docs authorizing/reporting acquisitions ARE board decisions (3);
# budget/capital funding is budget_allocation (3); pressure is chatter (1).
LABEL_TO_SIGNAL_TYPE = {
    "procurement_intent": "board_decision",
    "funding_intent": "budget_allocation",
    "pressure_signal": "political_pressure",
}
STAMP = "upstream-intent@v1"


def _write_signal(doc: dict, board_name: str, c: dict, resolve_org) -> bool:
    """Insert one Wave A signal via the production payload builder (grades,
    org resolution, unresolved flagging all reused). Idempotent per
    (document, title): a re-run skips existing rows."""
    from .signal_extractor import build_signal_payload
    title = f"{c['label']}: {(doc.get('title') or '')[:150]}"
    existing = supabase_client.fetch_rows_where(
        "signals", "id", {"document_id": f"eq.{doc['id']}",
                          "title": f"eq.{title[:200]}"}, limit=1)
    if existing:
        return False
    raw = {
        "signal_type": LABEL_TO_SIGNAL_TYPE[c["label"]],
        "title": title,
        "summary": c.get("rationale") or "",
        "quote_or_line": (c.get("evidence") or "")[:500],
        "organization_name": board_name,
        "confidence": "probable",
    }
    payload = build_signal_payload(raw, doc["id"], STAMP, resolve_org,
                                   lambda s: None, doc_type="board_minutes")
    supabase_client.insert_signal(payload)
    return True


def run(per_board: int, dry_run: bool = True) -> dict:
    import anthropic
    from .signal_extractor import build_resolver
    client = anthropic.Anthropic()
    resolve_org = build_resolver(
        supabase_client.fetch_rows("organizations", "id,canonical_name,aliases"),
        key_fields=("canonical_name",), alias_field="aliases")
    totals = Counter()
    per = defaultdict(Counter)
    for name, marker in BOARDS:
        docs = board_docs(marker, per_board)
        print(f"[{name}] {len(docs)} corpus docs (newest first)")
        for d in docs:
            try:
                c = classify(client, d.get("title") or "", d.get("content") or "")
            except Exception as e:
                print(f"  CLASSIFY ERROR: {type(e).__name__}: {str(e)[:140]}")
                per[name]["error"] += 1
                totals["error"] += 1
                continue
            per[name][c["label"]] += 1
            totals[c["label"]] += 1
            if c["label"] != "noise":
                print(f"  {c['label'].upper():18s} conf={c.get('confidence')} "
                      f":: {(d.get('title') or '')[:70]}")
                print(f"    evidence: {c.get('evidence','')[:160]}")
                print(f"    url: {(d.get('url') or '')[:110]}")
                if not dry_run:
                    try:
                        if _write_signal(d, name, c, resolve_org):
                            totals["written"] += 1
                        else:
                            totals["skipped_existing"] += 1
                    except Exception as e:
                        print(f"    WRITE ERROR: {type(e).__name__}: {str(e)[:140]}")
                        totals["write_error"] += 1
    print("=" * 72)
    for name, _ in BOARDS:
        c = per[name]
        n = sum(c.values()) or 1
        nn = n - c["noise"] - c["error"]
        print(f"VALIDATION [wave-a:{name}]: docs={sum(c.values())} "
              f"non_noise={nn} ({round(100*nn/n)}%) labels={dict(c)}")
    print(f"WAVE-A TOTALS: {dict(totals)} (DRY RUN, no signals written)"
          if dry_run else f"WAVE-A TOTALS: {dict(totals)}")
    return dict(totals)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wave A corpus intent pass")
    parser.add_argument("--per-board", type=int, default=8)
    parser.add_argument("--apply", action="store_true",
                        help="write signals (operator-approved 2026-07-26); "
                             "default is dry-run")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(per_board=args.per_board, dry_run=not args.apply)
    sys.exit(0)
