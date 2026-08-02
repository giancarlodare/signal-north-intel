"""SOURCING EXPANSION PROBE: fire / paramedic-EMS / defence (operator
2026-08-02). Read-only: corpus queries plus robots.txt GETs. Writes nothing,
calls no LLM, fetches no content pages.

The question it answers, per domain: what is already IN the corpus and merely
uncategorized, versus what is genuinely absent -- and for absent, whether the
absence is at the source or at our own keep-filter.

THE EPISTEMIC SPLIT THAT SHAPES EVERY NUMBER HERE (verified in source):
  - board_minutes.py keeps agenda items UNFILTERED (keywords only tag
    defence_relevant, never drop). For council/board sources the corpus
    read below measures true in-corpus availability.
  - canadabuys (via main.py), rss_collector, and every tenders_* portal
    collector apply the keywords.txt KEEP filter. Fire carries 6 terms and
    EMS 4, so domain material at those sources was largely DROPPED AT
    COLLECTION. Counts below are a FLOOR: they show only what happened to
    match some other keyword or a UNSPSC segment (46/92).

Sections:
  S1  Sources inventory: what is actually running, so "already collected"
      claims are checked against the sources table rather than memory.
  S2  FIRE: the four unlock doc types (master plans, community risk
      assessments, E&R by-laws, annual reports) + apparatus/PPE vocabulary,
      counted in the corpus with per-source attribution.
  S3  PARAMEDIC/EMS: response time performance plans, master/deployment
      plans, community paramedicine + clinical/fleet vocabulary.
  S4  DEFENCE: ACAN / RFI / LOI distribution recovered from the
      "Notice type:" line canadabuys stores in content (doc_type collapses
      them all to tender_notice -- src/main.py:189), plus platform and
      contracting vocabulary.
  S5  ROBOTS posture for the candidate new sources (robots.txt only; no
      content pages are fetched).
  S6  Recoverable arc material per domain, same shape as the three-
      constraints estimates: dated %, deep-linkable %, buyer-attributable %,
      distinct buyers, buyers with >=2 docs.
  S7  Categorization state: of the domain docs found, how many carry at
      least one categorized signal today.

Matching here is ilike SUBSTRING, deliberately: this is a recall probe, not
the keep-filter. Terms below are chosen to be distinctive enough that the
Bendix class ('ems' inside "Systems") cannot recur; anything still ambiguous
is labelled ~approx in the output.
"""
import os
import sys
import urllib.robotparser
from collections import Counter

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
from src import supabase_client as sc  # noqa: E402
from arc_census import is_deep_linkable  # noqa: E402

UA = "SignalNorthIntel/1.0"

# --- what we look for --------------------------------------------------------

# label -> list of ilike phrases (any match counts, deduped per doc)
FIRE_DOC_TYPES = {
    "Fire Master Plan": ["fire master plan"],
    "Community Risk Assessment": ["community risk assessment"],
    "Establishing & Regulating By-law": ["establishing and regulating"],
    "Annual fire report to council (~approx)": [
        "fire department annual report", "annual report of the fire",
        "fire services annual report", "fire service annual report"],
}
FIRE_VOCAB = [
    "pumper", "aerial ladder", "ladder truck", "quint", "tanker",
    "bunker gear", "turnout gear", "SCBA",
    "self-contained breathing apparatus", "AFFF", "firefighting foam",
    "fluorine-free foam", "hydraulic rescue", "extrication",
    "thermal imaging", "fire station", "apparatus bay", "training tower",
    "live fire training", "NFPA", "fire dispatch", "station alerting",
    "fire prevention", "mutual aid", "automatic aid", "fire chief",
]
EMS_DOC_TYPES = {
    "Response Time Performance Plan": ["response time performance plan"],
    "Paramedic Service Master Plan": [
        "paramedic service master plan", "paramedic services master plan"],
    "Deployment plan (~approx)": ["deployment plan"],
    "Community paramedicine": ["community paramedicine"],
}
EMS_VOCAB = [
    "power stretcher", "power cot", "stair chair", "monitor defibrillator",
    "cardiac monitor", "mechanical CPR", "ePCR",
    "electronic patient care record", "ambulance dispatch",
    "Central Ambulance Communications", "CACC", "chassis remount",
    "bariatric ambulance", "paramedic response unit", "land ambulance",
    "paramedic station", "ambulance base", "Ambulance Act", "base hospital",
    "chief of paramedic services",
]
DEFENCE_DOC_TYPES = {
    "Defence Investment Plan": ["defence investment plan"],
    "Departmental Plan / Results (~approx)": [
        "departmental plan", "departmental results report"],
    "Estimates (~approx)": ["main estimates", "supplementary estimates"],
    "NDDN / Senate defence committee": [
        "standing committee on national defence",
        "national security and defence"],
    "PBO / AG on defence (~approx)": [
        "parliamentary budget officer", "auditor general"],
    "IDEaS": ["innovation for defence excellence", "IDEaS program"],
}
DEFENCE_VOCAB = [
    "Canadian Surface Combatant", "River-class", "patrol submarine",
    "P-8 Poseidon", "CP-140", "F-35", "Griffon", "Cyclone helicopter",
    "Logistics Vehicle Modernization", "Armoured Combat Support",
    "NORAD", "North Warning System", "over-the-horizon radar",
    "Strong Secure Engaged", "Our North Strong and Free",
    "industrial and technological benefits", "in-service support",
    "counter-UAS", "electronic warfare", "SATCOM", "industry day",
    "sole source", "standing offer", "supply arrangement",
]

# The "Notice type:" values CanadaBuys prints, counted server-side. This is
# how ACANs/RFIs are recovered despite doc_type collapsing to tender_notice.
CANADABUYS_NOTICE_TYPES = [
    "Advance Contract Award Notice",
    "Request for Information",
    "Letter of Interest",
    "Request for Proposal",
    "Request for Quotation",
    "Invitation to Qualify",
    "Request for Standing Offer",
    "Request for Supply Arrangement",
    "Tender Notice",
]

# host -> representative paths we would actually read
ROBOTS_CANDIDATES = {
    "www.ontario.ca": [           # OFM + Ministry of Health EHS branch
        "/page/office-fire-marshal",
        "/page/emergency-health-services",
        "/laws/regulation/180378",
    ],
    "www.oafc.on.ca": ["/"],      # Ontario Association of Fire Chiefs
    "oapc.ca": ["/"],             # Ontario Association of Paramedic Chiefs
    "www.canada.ca": [            # DND plans, IDEaS, estimates
        "/en/department-national-defence.html",
        "/en/department-national-defence/services/procurement.html",
    ],
    "www.ourcommons.ca": ["/Committees/en/NDDN"],
    "sencanada.ca": ["/en/committees/secd/"],
    "www.pbo-dpb.ca": ["/en/"],
    "www.oag-bvg.gc.ca": ["/internet/English/"],
}

META = ("id,source_id,doc_type,status,url,title,published_on,buyer_name")


def _hits(phrase: str) -> list[dict]:
    """Metadata-only rows whose title or content contains the phrase."""
    pat = f"*{phrase}*"
    return sc.fetch_all_rows_where(
        "documents", META,
        {"or": f"(title.ilike.{pat},content.ilike.{pat})"})


def _collect(labelled: dict[str, list[str]]) -> tuple[dict, dict]:
    """Per-label doc dicts (deduped) and the union across labels."""
    per_label: dict[str, dict] = {}
    union: dict = {}
    for label, phrases in labelled.items():
        found: dict = {}
        for p in phrases:
            for d in _hits(p):
                found[d["id"]] = d
        per_label[label] = found
        union.update(found)
    return per_label, union


def _vocab_counts(terms: list[str]) -> tuple[list[tuple[str, int]], dict]:
    rows = []
    union: dict = {}
    for t in terms:
        found = {d["id"]: d for d in _hits(t)}
        rows.append((t, len(found)))
        union.update(found)
    return rows, union


def _per_source(docs: dict, source_names: dict) -> Counter:
    c: Counter = Counter()
    for d in docs.values():
        c[source_names.get(d.get("source_id"), d.get("source_id"))] += 1
    return c


def _arc_shape(domain: str, docs: dict, categorized_doc_ids: set) -> None:
    n = len(docs)
    print(f"\n  {domain}: recoverable arc material ({n} docs in corpus)")
    if not n:
        print("    nothing in corpus; nothing to shape")
        return
    dated = sum(1 for d in docs.values() if d.get("published_on"))
    deep = sum(1 for d in docs.values() if is_deep_linkable(d.get("url") or ""))
    buyer = sum(1 for d in docs.values() if (d.get("buyer_name") or "").strip())
    buyers = Counter((d.get("buyer_name") or "").strip()
                     for d in docs.values()
                     if (d.get("buyer_name") or "").strip())
    cat = sum(1 for i in docs if i in categorized_doc_ids)
    print(f"    dated: {dated}/{n} ({100*dated/n:.0f}%)   "
          f"deep-linkable: {deep}/{n} ({100*deep/n:.0f}%)")
    print(f"    buyer-attributable: {buyer}/{n} ({100*buyer/n:.0f}%)   "
          f"distinct buyers: {len(buyers)}   "
          f"buyers with >=2 docs: {sum(1 for v in buyers.values() if v >= 2)}")
    print(f"    docs already carrying a categorized signal: {cat}/{n}")
    if buyers:
        top = ", ".join(f"{b} ({v})" for b, v in buyers.most_common(6))
        print(f"    top buyers: {top}")


def robots_report() -> None:
    print("\n" + "=" * 78)
    print("S5  ROBOTS POSTURE (robots.txt only; no content pages fetched)")
    print("=" * 78)
    for host, paths in ROBOTS_CANDIDATES.items():
        url = f"https://{host}/robots.txt"
        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        except Exception as e:
            print(f"  {host:24s} UNREACHABLE ({e.__class__.__name__}) "
                  f"-- treat as unknown, not as permitted")
            continue
        if resp.status_code == 404:
            print(f"  {host:24s} no robots.txt (404): crawling permitted by "
                  f"default; honour it if one ever appears")
            continue
        if resp.status_code != 200:
            print(f"  {host:24s} robots.txt HTTP {resp.status_code} "
                  f"-- treat as unknown, not as permitted")
            continue
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(resp.text.splitlines())
        verdicts = []
        for p in paths:
            ok = rp.can_fetch(UA, f"https://{host}{p}")
            verdicts.append(f"{p} {'ALLOWED' if ok else 'DISALLOWED'}")
        delay = rp.crawl_delay(UA)
        extra = f"   crawl-delay={delay}s" if delay else ""
        print(f"  {host:24s} " + "; ".join(verdicts) + extra)


def main() -> None:
    print("SOURCING EXPANSION PROBE -- fire / EMS / defence, read-only")

    print("\n" + "=" * 78)
    print("S1  SOURCES INVENTORY (what is actually running)")
    print("=" * 78)
    sources = sc.fetch_rows("sources", "id,name,url,source_type,jurisdiction")
    source_names = {s["id"]: s.get("name") for s in sources}
    for s in sorted(sources, key=lambda x: str(x.get("name"))):
        print(f"  [{s.get('jurisdiction')}] {s.get('name')}   {s.get('url')}")

    # One pass over signals so S7 can say which found docs are categorized.
    sig_rows = sc.fetch_all_rows_where(
        "signals", "id,document_id,categories(slug)", {"suppressed": "is.false"})
    categorized_doc_ids = {
        s.get("document_id") for s in sig_rows
        if s.get("categories") and (
            s["categories"][0].get("slug") if isinstance(s["categories"], list)
            else s["categories"].get("slug"))
    }

    for title, doc_types, vocab, key in (
        ("S2  FIRE", FIRE_DOC_TYPES, FIRE_VOCAB, "fire"),
        ("S3  PARAMEDIC / EMS", EMS_DOC_TYPES, EMS_VOCAB, "ems"),
        ("S4  DEFENCE", DEFENCE_DOC_TYPES, DEFENCE_VOCAB, "defence"),
    ):
        print("\n" + "=" * 78)
        print(f"{title}")
        print("=" * 78)
        per_label, union = _collect(doc_types)
        print("  Document types sought:")
        for label, found in per_label.items():
            srcs = _per_source(found, source_names)
            where = ("  <- " + ", ".join(f"{k} ({v})" for k, v in
                                         srcs.most_common(4))) if srcs else ""
            print(f"    {label:42s} {len(found):5d}{where}")
        vocab_rows, vocab_union = _vocab_counts(vocab)
        print("  Vocabulary probe (ilike, upper bound per term):")
        for t, n in sorted(vocab_rows, key=lambda x: -x[1]):
            if n:
                print(f"    {t:42s} {n:5d}")
        zero = [t for t, n in vocab_rows if not n]
        if zero:
            print(f"    zero hits: {', '.join(zero)}")
        union.update(vocab_union)
        _arc_shape(title.split(None, 1)[1], union, categorized_doc_ids)

    print("\n" + "=" * 78)
    print("S4b CANADABUYS 'Notice type:' DISTRIBUTION (whole corpus)")
    print("    doc_type collapses all of these to tender_notice; the line in")
    print("    content is the only place the distinction survives.")
    print("=" * 78)
    for nt in CANADABUYS_NOTICE_TYPES:
        rows = sc.fetch_all_rows_where(
            "documents", "id",
            {"content": f"ilike.*Notice type: {nt}*"})
        print(f"  {nt:36s} {len(rows):6d}")

    robots_report()
    print("\nprobe complete (read-only; nothing written)")


if __name__ == "__main__":
    main()
