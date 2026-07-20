"""Thin REST client for the handful of Supabase operations this collector
needs. Uses the PostgREST API directly (via `requests`) rather than the
supabase-py package, so there's only one thing to debug if a call fails:
the HTTP response printed in the raised error.
"""
import logging
from datetime import date, datetime
from typing import Any

import requests

from . import config

log = logging.getLogger(__name__)


class SupabaseError(RuntimeError):
    pass


def _headers(prefer: str | None = None) -> dict:
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_ROLE_KEY:
        raise SupabaseError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set. "
            "These must be provided as environment variables (GitHub Actions "
            "secrets in production)."
        )
    headers = {
        "apikey": config.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _json_default(obj: Any):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _request(method: str, path: str, **kwargs) -> requests.Response:
    url = f"{config.SUPABASE_URL}/rest/v1/{path}"
    resp = requests.request(method, url, timeout=config.REQUEST_TIMEOUT_SECONDS, **kwargs)
    if resp.status_code >= 400:
        raise SupabaseError(
            f"{method} {path} failed with {resp.status_code}: {resp.text}"
        )
    return resp


def update_source_last_collected(source_id: str, when: datetime) -> None:
    _request(
        "PATCH",
        "sources",
        headers=_headers(),
        params={"id": f"eq.{source_id}"},
        json={"last_collected_at": when.isoformat()},
    )


def get_document_by_hash(content_hash: str) -> dict | None:
    resp = _request(
        "GET",
        "documents",
        headers=_headers(),
        params={"select": "id", "content_hash": f"eq.{content_hash}", "limit": 1},
    )
    rows = resp.json()
    return rows[0] if rows else None


def insert_document(payload: dict) -> dict:
    resp = _request(
        "POST",
        "documents",
        headers=_headers(prefer="return=representation"),
        data=_dumps(payload),
    )
    rows = resp.json()
    return rows[0]


def find_or_create_vendor(raw_name: str) -> str | None:
    """Ensure a vendor exists in the vendors table, returning its id.

    Idempotent by design: we look up by the SAME name we would store (so a
    vendor seen twice is found the second time), match against aliases too,
    and insert with an ON CONFLICT clause so a duplicate can never raise -
    the vendors.canonical_name unique constraint is respected rather than
    tripped over.
    """
    name = " ".join((raw_name or "").split())
    if not name:
        return None
    # Exact-match lookup with eq, NOT a quoted ilike pattern: PostgREST treats
    # a double-quoted like/ilike value literally (the quotes join the pattern),
    # so the quoted form silently never matched. Every repeat vendor missed
    # this lookup, fell through to the ignore-duplicates insert whose body is
    # empty on a duplicate, and the award linked vendor_id=None (issue #74).
    # eq needs no quoting here: a plain column filter takes everything after
    # "eq." as the value, commas and parentheses included. Same fix as
    # resolve_orgs._fetch_org. The aliases containment filter keeps its quotes:
    # that is array-literal syntax, not pattern quoting.
    for params in (
        {"select": "id", "canonical_name": f"eq.{name}", "limit": 1},
        {"select": "id", "aliases": f'cs.{{"{name.replace(chr(34), "")}"}}', "limit": 1},
    ):
        rows = _request("GET", "vendors", headers=_headers(), params=params).json()
        if rows:
            return rows[0]["id"]

    # Insert, ignoring (not erroring on) a duplicate canonical_name that may
    # have been created concurrently. return=representation gives us the row
    # back on a fresh insert; on an ignored duplicate the body is empty, so
    # re-fetch rather than returning None (a lost race must still link).
    rows = _request(
        "POST",
        "vendors?on_conflict=canonical_name",
        headers=_headers(prefer="resolution=ignore-duplicates,return=representation"),
        data=_dumps({"canonical_name": name, "aliases": []}),
    ).json()
    if rows:
        return rows[0]["id"]
    refetch = _request("GET", "vendors", headers=_headers(),
                       params={"select": "id", "canonical_name": f"eq.{name}",
                               "limit": 1}).json()
    return refetch[0]["id"] if refetch else None


def insert_contract_award(payload: dict) -> dict:
    resp = _request(
        "POST",
        "contract_awards",
        headers=_headers(prefer="return=representation"),
        data=_dumps(payload),
    )
    return resp.json()[0]


def get_documents_by_status(status: str, limit: int,
                            select: str = "id,title,doc_type,url,published_on,source_id,content",
                            doc_type: str | None = None,
                            doc_types: list | None = None,
                            order: str | None = None) -> list:
    """Fetch captured/extracted/failed documents. Pass `doc_type` for one type or
    `doc_types` for several (PostgREST `in.(...)`); `order` is a PostgREST order
    clause (e.g. "published_on.desc.nullslast") to control which documents a
    capped run processes first."""
    params = {"select": select, "status": f"eq.{status}", "limit": limit}
    if doc_type:
        params["doc_type"] = f"eq.{doc_type}"
    elif doc_types:
        params["doc_type"] = f"in.({','.join(doc_types)})"
    if order:
        params["order"] = order
    resp = _request("GET", "documents", headers=_headers(), params=params)
    return resp.json()


def update_document_status(document_id: str, status: str, error_detail: str | None = None) -> None:
    payload: dict = {"status": status}
    if error_detail is not None:
        payload["error_detail"] = error_detail
    _request(
        "PATCH",
        "documents",
        headers=_headers(),
        params={"id": f"eq.{document_id}"},
        json=payload,
    )


def insert_signal(payload: dict) -> dict:
    resp = _request(
        "POST",
        "signals",
        headers=_headers(prefer="return=representation"),
        data=_dumps(payload),
    )
    return resp.json()[0]


def get_source_name(source_id: str) -> str:
    resp = _request(
        "GET",
        "sources",
        headers=_headers(),
        params={"select": "name", "id": f"eq.{source_id}", "limit": 1},
    )
    rows = resp.json()
    return rows[0]["name"] if rows else "Unknown"


def fetch_rows(table: str, select: str, limit: int = 10000) -> list:
    """Fetch rows from a table (used to build in-memory lookup caches)."""
    resp = _request(
        "GET",
        table,
        headers=_headers(),
        params={"select": select, "limit": limit},
    )
    return resp.json()


def fetch_rows_where(table: str, select: str, filters: dict, limit: int = 10000,
                     offset: int = 0) -> list:
    """Fetch rows with PostgREST filters, e.g. {"status": "eq.captured",
    "created_at": "gte.2026-06-11"}."""
    params = {"select": select, "limit": limit, **filters}
    if offset:
        params["offset"] = offset
    resp = _request("GET", table, headers=_headers(), params=params)
    return resp.json()


def fetch_all_rows_where(table: str, select: str, filters: dict,
                         page_size: int = 1000) -> list:
    """Page through every matching row. PostgREST silently caps a single
    response at the server's max-rows (1,000 by default), so one large-limit
    request quietly truncates once a table grows past that."""
    rows: list = []
    offset = 0
    while True:
        batch = fetch_rows_where(table, select, filters, limit=page_size, offset=offset)
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        offset += page_size


def insert_row(table: str, payload: dict) -> dict:
    resp = _request(
        "POST",
        table,
        headers=_headers(prefer="return=representation"),
        data=_dumps(payload),
    )
    return resp.json()[0]


def update_row(table: str, row_id: str, payload: dict) -> None:
    _request(
        "PATCH",
        table,
        headers=_headers(),
        params={"id": f"eq.{row_id}"},
        data=_dumps(payload),
    )


def delete_rows(table: str, filters: dict) -> None:
    """Delete rows matching PostgREST filters, e.g. {"id": "eq.<uuid>"}. Requires
    at least one filter so a bare DELETE can never wipe a whole table."""
    if not filters:
        raise SupabaseError("delete_rows requires at least one filter (refusing a table-wide delete)")
    _request("DELETE", table, headers=_headers(), params=filters)


def _dumps(payload: dict) -> bytes:
    import json

    return json.dumps(payload, default=_json_default).encode("utf-8")
