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
from .vendors import normalize_vendor_name

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


def find_or_create_vendor(raw_name: str) -> str:
    normalized = normalize_vendor_name(raw_name)

    resp = _request(
        "GET",
        "vendors",
        headers=_headers(),
        params={"select": "id", "canonical_name": f"ilike.{normalized}", "limit": 1},
    )
    rows = resp.json()
    if rows:
        return rows[0]["id"]

    # PostgREST "contains" filter on a text[] aliases column.
    resp = _request(
        "GET",
        "vendors",
        headers=_headers(),
        params={"select": "id", "aliases": f"cs.{{{normalized}}}", "limit": 1},
    )
    rows = resp.json()
    if rows:
        return rows[0]["id"]

    log.info("No existing vendor matched %r - creating a new vendor row.", raw_name)
    resp = _request(
        "POST",
        "vendors",
        headers=_headers(prefer="return=representation"),
        data=_dumps({"canonical_name": raw_name, "aliases": []}),
    )
    return resp.json()[0]["id"]


def insert_contract_award(payload: dict) -> dict:
    resp = _request(
        "POST",
        "contract_awards",
        headers=_headers(prefer="return=representation"),
        data=_dumps(payload),
    )
    return resp.json()[0]


def _dumps(payload: dict) -> bytes:
    import json

    return json.dumps(payload, default=_json_default).encode("utf-8")
