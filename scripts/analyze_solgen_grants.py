"""SOLGEN grant-capture analysis (Synapse Tier-1 targeting, strategy/analysis).

Source: https://www.ontario.ca/page/current-community-safety-project-grant-recipients
the authoritative per-service Ministry of the Solicitor General grant-award
ledger (server-side Drupal; publisher-official). Read-only, robots honored.

Builds a per-service grant-capture table for Ontario police services:
- total awarded across all streams, number of streams present, distinct projects;
- the ELIGIBLE-BUT-ABSENT streams (weighted by whether a stream is formula /
  allocation-driven vs open-competition, so the ROI model stays peer-cohort
  relative, not fantasy relative).
Then two ranked views: (a) present-in-some / missing-others (money on the
table), and (b) cross-referenced against our police-service roster from the DB
(boards/tenders orgs), services ABSENT from the page entirely (warmest leads).

No writes; prints the artifact.

    python scripts/analyze_solgen_grants.py
"""
import re
import sys
from collections import defaultdict
from html.parser import HTMLParser

sys.path.insert(0, ".")

from src.board_minutes import PoliteFetcher
from src import supabase_client

PAGE = "https://www.ontario.ca/page/current-community-safety-project-grant-recipients"

# Stream design: which are formula/allocation (guaranteed-ish, absence = a real
# unclaimed gap) vs open-competition (absence = opportunity, not entitlement).
# Matched loosely against table headings.
STREAM_TYPE = [
    ("community safety and policing", "csp", None),   # refined below by local/provincial
    ("proceeds of crime", "competition", "Proceeds of Crime Front-Line"),
    ("victim", "competition", "Victim Support"),
    ("safer and vital", "competition", "Safer and Vital Communities"),
]
MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.cur_h = [], ""
        self._h = self._buf = self._row = self._tbl = None
        self._incell = False

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4"):
            self._h = []
        elif tag == "table":
            self._tbl = {"heading": self.cur_h, "rows": []}
        elif tag == "tr" and self._tbl is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._buf, self._incell = [], True

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4") and self._h is not None:
            self.cur_h = " ".join("".join(self._h).split())[:90]
            self._h = None
        elif tag in ("td", "th") and self._incell:
            self._row.append(" ".join("".join(self._buf).split()))
            self._incell = False
        elif tag == "tr" and self._row is not None:
            if any(c.strip() for c in self._row):
                self._tbl["rows"].append(self._row)
            self._row = None
        elif tag == "table" and self._tbl is not None:
            self.tables.append(self._tbl)
            self._tbl = None

    def handle_data(self, data):
        if self._incell:
            self._buf.append(data)
        elif self._h is not None:
            self._h.append(data)


def _amount(cells):
    best = 0.0
    for c in cells:
        m = MONEY.search(c)
        if m:
            try:
                best = max(best, float(m.group(1).replace(",", "")))
            except ValueError:
                pass
    return best


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _stream_label(heading):
    h = heading.lower()
    if "community safety and policing" in h or "csp" in h:
        kind = "provincial" if "provincial" in h else ("local" if "local" in h else "csp")
        return f"CSP {kind}", ("formula" if kind == "local" else "competition")
    for key, typ, label in STREAM_TYPE:
        if key in h:
            return label or key.title(), typ
    return heading[:40] or "unlabeled", "competition"


def main():
    fetcher = PoliteFetcher()
    if not fetcher.allowed(PAGE):
        print("robots DISALLOWED; abort.")
        return
    r = fetcher.get(PAGE)
    if r is None:
        print("fetch returned None; abort.")
        return
    parser = Tables()
    parser.feed(r.text or "")
    print(f"page bytes={len(r.text)} tables={len(parser.tables)}")

    # Per-service aggregation across all stream tables.
    per = defaultdict(lambda: {"total": 0.0, "streams": set(), "projects": 0})
    streams_seen = {}
    for t in parser.tables:
        label, typ = _stream_label(t["heading"])
        rows = t["rows"]
        if len(rows) < 2:
            continue
        streams_seen[label] = typ
        # skip the header row; recipient = first cell, amount = money cell
        body = rows[1:] if any(MONEY.search(c) for c in rows[0]) is None else rows
        for row in rows:
            name = _norm(row[0])
            amt = _amount(row)
            if not name or amt <= 0 or "total" in name or "recipient" in name:
                continue
            per[name]["total"] += amt
            per[name]["streams"].add(label)
            per[name]["projects"] += 1
    print(f"streams: {streams_seen}")
    print(f"distinct recipients (all types): {len(per)}")

    # Our police roster from the DB (boards + services).
    orgs = supabase_client.fetch_rows("organizations",
                                      "id,canonical_name,aliases,org_type")
    police = [o for o in orgs if (o.get("org_type") or "") in
              ("police_service", "police_board")]
    print(f"police orgs in roster: {len(police)}")

    def match(recip_norm):
        for o in police:
            names = [o["canonical_name"]] + (o.get("aliases") or [])
            for nm in names:
                nn = _norm(nm)
                if nn and (nn in recip_norm or recip_norm in nn):
                    return o["canonical_name"]
        return None

    # POLICE recipients on the page (matched to roster) + the total captured.
    print("=" * 74)
    print("VIEW A: police services PRESENT on the ledger (capture + missing streams)")
    all_streams = set(streams_seen)
    formula_streams = {s for s, t in streams_seen.items() if t == "formula"}
    present = []
    for name, d in per.items():
        canon = match(name)
        if not canon:
            continue
        missing = all_streams - d["streams"]
        missing_formula = missing & formula_streams
        present.append((canon, d["total"], sorted(d["streams"]), sorted(missing),
                        sorted(missing_formula)))
    for canon, total, got, missing, missf in sorted(present, key=lambda x: -x[1]):
        flag = f"  [MISSING FORMULA: {missf}]" if missf else ""
        print(f"  {canon:38s} ${total:>12,.0f}  streams={got}  missing={missing}{flag}")
    matched_canon = {p[0] for p in present}

    print("=" * 74)
    print("VIEW B: roster police services ABSENT from the ledger (warmest Tier-1 leads)")
    for o in sorted(police, key=lambda o: o["canonical_name"]):
        if o["canonical_name"] not in matched_canon:
            print(f"  {o['canonical_name']}  ({o.get('org_type')})")

    print("=" * 74)
    print("Note: 'formula' streams (CSP local allocation) are entitlement-like, so "
          "absence is unclaimed money; 'competition' streams are opportunity, not "
          "entitlement. ROI must stay peer-cohort relative.")
    print("Roster is our current SN coverage (boards/tenders orgs), NOT all ~44 "
          "Ontario police services; a fuller roster widens View B.")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
    sys.exit(0)
