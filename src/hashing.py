import hashlib


def content_hash(*parts: str) -> str:
    """Stable hash of a document's identifying fields.

    Used so re-running the collector never inserts duplicate rows: we hash
    the notice's reference number + doc_type (falling back to url + title
    if no reference number is available) and check for an existing row
    with that hash before inserting.
    """
    normalized = "|".join((p or "").strip().lower() for p in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
