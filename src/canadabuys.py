"""Download and parse CanadaBuys open-data CSV files.

CanadaBuys column headers are bilingual, e.g. "title-titre-eng" /
"title-titre-fra", and PSPC has tweaked exact header spellings between
schema revisions. Rather than hard-code header strings that could go stale,
we match headers by substring so a minor renaming doesn't silently break
the collector.
"""
import csv
import io
import logging
from typing import Iterable

import requests

from . import config

log = logging.getLogger(__name__)
# canadabuys.canada.ca returns 403 to the default python-requests User-Agent,
# even for these public open-data files. A normal browser UA is enough to
# get through.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

class CsvSchemaError(RuntimeError):
    """Raised when a required column can't be located in a downloaded CSV."""


def fetch_csv_rows(url: str) -> list[dict]:
    resp = requests.get(url, headers=_HEADERS, timeout=config.REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    # CanadaBuys CSVs are UTF-8 with a BOM.
    text = resp.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    log.info("Downloaded %d rows from %s", len(rows), url)
    if rows:
        log.info("Columns found: %s", list(rows[0].keys()))
    return rows


def find_column(fieldnames: Iterable[str], *substrings: str, prefer_suffix: str = "-eng") -> str | None:
    """Find a column whose name contains all given substrings (case-insensitive).

    When multiple candidates match (typically an -eng/-fra bilingual pair),
    prefer the one ending in `prefer_suffix`.
    """
    candidates = []
    for name in fieldnames:
        lname = name.lower()
        if all(s.lower() in lname for s in substrings):
            candidates.append(name)
    if not candidates:
        return None
    for c in candidates:
        if c.lower().endswith(prefer_suffix):
            return c
    return candidates[0]


def require_column(fieldnames: Iterable[str], *substrings: str, **kwargs) -> str:
    col = find_column(fieldnames, *substrings, **kwargs)
    if col is None:
        raise CsvSchemaError(
            f"Could not find a column matching {substrings!r} in CSV headers: "
            f"{list(fieldnames)!r}. CanadaBuys may have renamed a column - "
            f"update src/canadabuys.py."
        )
    return col
