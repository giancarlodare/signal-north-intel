"""Layer-1 salary ledger: Sunshine List + StatCan Police Administration
Survey (operator go 2026-08-02; design: docs/sunshine-list-design.md).

Downloads, not scrapes: both sources publish structured files. No LLM is
called anywhere in this module and no extraction path reads these tables.

  Sunshine  data.ontario.ca CKAN dataset `public-sector-salary-disclosure`.
            The CKAN API (package_show) lists one resource per disclosure
            year, so nothing here hardcodes a resource id that rots. Rows
            are filtered AT INGEST to public-safety employers (design D2:
            re-widenable later without loss because the files remain
            downloadable, unlike the tender keep-filter).
  StatCan   Police resources table (35-10-0076 with 35-10-0046 fallback)
            via the Web Data Service full-table CSV. Ontario rows land in
            long format (year, service, metric, value).

Discipline: idempotent upserts on the natural keys; a year-file that fails
to parse RAISES (a partial year never lands silently); pre-migration the
run reports and exits nonzero so a scheduled run cannot claim success while
writing nothing.

Usage:
    python -m src.salary_ledger --dry-run              # download+parse+report
    python -m src.salary_ledger --apply                # ingest all years
    python -m src.salary_ledger --apply --years 2024,2023
"""
import argparse
import csv
import io
import json
import logging
import re
import sys
import zipfile

import requests

from . import supabase_client as sc

log = logging.getLogger("salary_ledger")
UA = "SignalNorthIntel/1.0"
TIMEOUT = 120

CKAN_PACKAGE = ("https://data.ontario.ca/api/3/action/package_show"
                "?id=public-sector-salary-disclosure")
# Police resources (personnel + expenditures). Primary pid first; the older
# survey table as fallback because StatCan retires pids without redirects.
STATCAN_PIDS = ("35100076", "35100046")
STATCAN_WDS = ("https://www150.statcan.gc.ca/t1/wds/rest/"
               "getFullTableDownloadCSV/{pid}/en")

# Employer scope (design D2): matched case-insensitively against employer
# name. Deliberately broad within public safety; widening is a one-line
# change plus a re-run.
EMPLOYER_PAT = re.compile(
    r"police|fire|paramedic|ambulance|emergency (medical|health|services)"
    r"|911|9-1-1|public safety|solicitor general|correctional|corrections"
    r"|conservation officer|special investigations|forensic",
    re.IGNORECASE)
# Sunshine sector values that are always in scope regardless of employer
# wording (the OPP lives under the OPS sector, not a "police" employer name).
SECTOR_PAT = re.compile(r"justice|safety", re.IGNORECASE)


def _get(url: str) -> requests.Response:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z]", "", (h or "").lower())


# Header aliases seen across Sunshine year-files (the schema drifted over
# the years: "Salary Paid" vs "Salary", bilingual variants, etc.).
H_ALIASES = {
    "sector": {"sector"},
    "employer": {"employer"},
    "last_name": {"lastname", "surname"},
    "first_name": {"firstname", "givenname"},
    "position": {"jobtitle", "position", "positiontitle"},
    "salary_paid": {"salarypaid", "salary"},
    "taxable_benefits": {"taxablebenefits", "benefits"},
    "year": {"calendaryear", "year"},
}


def _map_headers(fieldnames: list[str]) -> dict:
    out = {}
    for fn in fieldnames or []:
        n = _norm_header(fn)
        for key, aliases in H_ALIASES.items():
            if n in aliases:
                out[key] = fn
    missing = {"employer", "last_name", "first_name", "position",
               "salary_paid"} - set(out)
    if missing:
        raise ValueError(f"unrecognized Sunshine header shape; missing {missing} "
                         f"in {fieldnames}")
    return out


def _money(v: str) -> float | None:
    v = (v or "").replace("$", "").replace(",", "").strip()
    if not v:
        return None
    return float(v)


def sunshine_resources() -> list[dict]:
    """CKAN resources for the dataset, newest year first, CSV/XLSX only."""
    pkg = _get(CKAN_PACKAGE).json()
    if not pkg.get("success"):
        raise RuntimeError(f"CKAN package_show failed: {json.dumps(pkg)[:300]}")
    out = []
    for r in pkg["result"]["resources"]:
        name = f"{r.get('name') or ''} {r.get('url') or ''}"
        m = re.search(r"(19|20)\d\d", name)
        fmt = (r.get("format") or "").lower()
        if m and fmt in ("csv", "xlsx"):
            out.append({"year": int(m.group(0)), "url": r["url"], "format": fmt})
    # One resource per year: prefer CSV when both formats exist.
    best: dict[int, dict] = {}
    for r in sorted(out, key=lambda x: x["format"]):  # csv sorts before xlsx
        best.setdefault(r["year"], r)
    return sorted(best.values(), key=lambda x: -x["year"])


def parse_sunshine_csv(text: str, year: int, source_url: str) -> tuple[list[dict], int]:
    """(in-scope rows, total rows read). Raises on an unrecognizable file."""
    reader = csv.DictReader(io.StringIO(text))
    cols = _map_headers(reader.fieldnames)
    rows, total = [], 0
    for rec in reader:
        total += 1
        employer = (rec.get(cols["employer"]) or "").strip()
        sector = (rec.get(cols.get("year", ""), "") and rec.get(cols.get("sector", ""), "") or
                  rec.get(cols.get("sector", ""), "") or "").strip() \
            if cols.get("sector") else ""
        if not employer:
            continue
        if not (EMPLOYER_PAT.search(employer) or (sector and SECTOR_PAT.search(sector))):
            continue
        salary = _money(rec.get(cols["salary_paid"]) or "")
        if salary is None:
            continue
        rows.append({
            "year": year,
            "sector": sector or None,
            "employer": employer,
            "last_name": (rec.get(cols["last_name"]) or "").strip(),
            "first_name": (rec.get(cols["first_name"]) or "").strip(),
            "position": (rec.get(cols["position"]) or "").strip(),
            "salary_paid": salary,
            "taxable_benefits": _money(rec.get(cols.get("taxable_benefits", ""), "")),
            "source_url": source_url,
        })
    if total == 0:
        raise ValueError(f"Sunshine {year}: zero rows parsed from {source_url}")
    return rows, total


def statcan_ontario_rows() -> tuple[list[dict], str]:
    """Long-format Ontario rows from the first police pid that responds."""
    last_err: Exception | None = None
    for pid in STATCAN_PIDS:
        try:
            meta = _get(STATCAN_WDS.format(pid=pid)).json()
            zip_url = meta.get("object")
            if meta.get("status") != "SUCCESS" or not zip_url:
                raise RuntimeError(f"WDS {pid}: {json.dumps(meta)[:200]}")
            blob = _get(zip_url).content
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                csv_name = next(n for n in z.namelist()
                                if n.endswith(".csv") and "MetaData" not in n)
                text = z.read(csv_name).decode("utf-8-sig")
            rows = []
            for rec in csv.DictReader(io.StringIO(text)):
                geo = rec.get("GEO") or ""
                if "ontario" not in geo.lower():
                    continue
                ref = rec.get("REF_DATE") or ""
                year = int(ref[:4]) if ref[:4].isdigit() else None
                val = rec.get("VALUE")
                if year is None:
                    continue
                dims = [v for k, v in rec.items()
                        if k not in ("REF_DATE", "GEO", "VALUE", "DGUID",
                                     "UOM", "UOM_ID", "SCALAR_FACTOR",
                                     "SCALAR_ID", "VECTOR", "COORDINATE",
                                     "STATUS", "SYMBOL", "TERMINATED",
                                     "DECIMALS") and v]
                rows.append({
                    "year": year,
                    "service": geo,
                    "metric": " | ".join(dims)[:500] or "(total)",
                    "value": float(val) if val not in (None, "", "..") else None,
                    "source_url": f"https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={pid}01",
                })
            if not rows:
                raise ValueError(f"pid {pid}: zero Ontario rows")
            return rows, pid
        except Exception as e:  # noqa: BLE001 - try the fallback pid, then raise
            last_err = e
            log.warning("StatCan pid %s failed (%s); trying fallback", pid, e)
    raise RuntimeError(f"all StatCan pids failed: {last_err}")


def _table_present(table: str) -> bool:
    try:
        sc.fetch_rows_where(table, "id", {}, limit=1)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("%s not present (%s); paste "
                  "migrations/2026-08-02_salary_ledger.sql first", table,
                  type(e).__name__)
        return False


def _upsert(table: str, conflict: str, rows: list[dict], batch: int = 500) -> int:
    written = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        sc._request(  # noqa: SLF001 - module-internal helper, same pattern as awards
            "POST", f"{table}?on_conflict={conflict}",
            headers=sc._headers(prefer="resolution=merge-duplicates"),
            data=sc._dumps(chunk))
        written += len(chunk)
    return written


def run(apply: bool, years: set[int] | None) -> int:
    stats = {"years": 0, "read": 0, "kept": 0, "written": 0, "errors": 0}

    for res in sunshine_resources():
        if years and res["year"] not in years:
            continue
        if res["format"] != "csv":
            # XLSX-only years exist early in the series; named loudly rather
            # than silently skipped, and revisited if the count matters.
            log.warning("Sunshine %s is %s-only; skipped this pass (named, "
                        "not silent)", res["year"], res["format"])
            continue
        text = _get(res["url"]).text
        rows, total = parse_sunshine_csv(text, res["year"], res["url"])
        stats["years"] += 1
        stats["read"] += total
        stats["kept"] += len(rows)
        log.info("Sunshine %s: read %d, in-scope %d", res["year"], total, len(rows))
        if apply and rows:
            stats["written"] += _upsert(
                "salary_disclosures",
                "year,employer,last_name,first_name,position", rows)

    sc_rows, pid = statcan_ontario_rows()
    log.info("StatCan pid %s: %d Ontario rows", pid, len(sc_rows))
    stats["read"] += len(sc_rows)
    stats["kept"] += len(sc_rows)
    if apply:
        stats["written"] += _upsert("police_admin_stats",
                                    "year,service,metric", sc_rows)

    log.info("VALIDATION salary_ledger: years=%(years)d read=%(read)d "
             "kept=%(kept)d written=%(written)d errors=%(errors)d", stats)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--years", default="",
                    help="comma-separated years; empty = every year available")
    args = ap.parse_args()
    years = {int(y) for y in args.years.split(",") if y.strip()} or None

    if args.apply and not (_table_present("salary_disclosures")
                           and _table_present("police_admin_stats")):
        return 1  # loud: an apply run against missing tables is a failure
    return run(apply=args.apply, years=years)


if __name__ == "__main__":
    sys.exit(main())
