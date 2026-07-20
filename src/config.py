import os
from datetime import date

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

# Your `sources` table has one row per CanadaBuys feed rather than a single
# shared row, so tender notices and award notices are attributed to
# different source_ids. Override via env vars if these rows are ever
# recreated with new ids.
TENDER_SOURCE_ID = os.environ.get("TENDER_SOURCE_ID", "5ff27bde-7c78-4a5a-8efe-a0be8ef84fc8")
AWARD_SOURCE_ID = os.environ.get("AWARD_SOURCE_ID", "0bce66c4-a58c-48b5-aede-6ae2b85ae890")

KEYWORDS_FILE = os.environ.get(
    "KEYWORDS_FILE",
    os.path.join(os.path.dirname(__file__), "..", "config", "keywords.txt"),
)

# Open data CSV endpoints (refreshed by PSPC most mornings before 8:30am ET).
NEW_TENDER_NOTICES_URL = (
    "https://canadabuys.canada.ca/opendata/pub/"
    "newTenderNotice-nouvelAvisAppelOffres.csv"
)
# The COMPLETE open-tenders file (every currently open notice, not just new
# ones): the backfill source for title-only tender documents. Override with
# OPEN_TENDER_NOTICES_URL if PSPC renames it; the backfill fails loud on 404.
OPEN_TENDER_NOTICES_URL = os.environ.get(
    "OPEN_TENDER_NOTICES_URL",
    "https://canadabuys.canada.ca/opendata/pub/tenderNotice-avisAppelOffres.csv",
)
# The award notices file is published per Canadian federal fiscal year
# (April 1 - March 31), e.g. "2026-2027-awardNotice-avisAttribution.csv".
# We compute the current fiscal year at runtime so this keeps working after
# each April 1 rollover without a code change. Override with the
# AWARD_NOTICES_URL env var if PSPC ever changes the naming pattern.
def _fiscal_year_start(today: date) -> int:
    """The calendar year in which the fiscal year covering `today` began."""
    return today.year if today.month >= 4 else today.year - 1


def _fiscal_year_string(start_year: int) -> str:
    return f"{start_year}-{start_year + 1}"


def _current_fiscal_year(today: date | None = None) -> str:
    return _fiscal_year_string(_fiscal_year_start(today or date.today()))


def _award_url_for(fiscal_year: str) -> str:
    return (
        "https://canadabuys.canada.ca/opendata/pub/"
        f"{fiscal_year}-awardNotice-avisAttribution.csv"
    )


# For a grace window after the April 1 fiscal-year rollover we ALSO collect
# the *previous* year's award file. CanadaBuys keeps publishing prior-year
# award notices for a while after the new year starts; once the current
# fiscal year flips on April 1 we stop reading that file, so those late
# entries would be lost forever. Re-reading the previous year's file during
# the window is harmless because inserts are deduped by content_hash.
AWARD_BACKFILL_GRACE_DAYS = int(os.environ.get("AWARD_BACKFILL_GRACE_DAYS", "60"))

# Single-URL override kept for backward compatibility / manual pinning.
_AWARD_NOTICES_URL_OVERRIDE = os.environ.get("AWARD_NOTICES_URL")


def award_notice_urls(today: date | None = None) -> list[str]:
    """Award-notice CSV URLs to collect on this run.

    Always the current fiscal year's file. Within AWARD_BACKFILL_GRACE_DAYS
    of the April 1 rollover, the previous fiscal year's file is appended too,
    to catch prior-year awards published after the rollover.
    """
    if _AWARD_NOTICES_URL_OVERRIDE:
        return [_AWARD_NOTICES_URL_OVERRIDE]
    today = today or date.today()
    start = _fiscal_year_start(today)
    urls = [_award_url_for(_fiscal_year_string(start))]
    days_since_rollover = (today - date(today.year, 4, 1)).days
    if 0 <= days_since_rollover < AWARD_BACKFILL_GRACE_DAYS:
        urls.append(_award_url_for(_fiscal_year_string(start - 1)))
    return urls


# The current fiscal year's award file (single URL). Retained for reference;
# the collector iterates award_notice_urls() so it also picks up the previous
# year's file during the post-rollover grace window.
AWARD_NOTICES_URL = _AWARD_NOTICES_URL_OVERRIDE or _award_url_for(_current_fiscal_year())

# URL templates for building a human-clickable link back to the notice on
# canadabuys.canada.ca, keyed on the notice's reference number. If the
# collector logs point to broken links, check the real URL pattern on the
# site and adjust these two lines.
TENDER_NOTICE_URL_TEMPLATE = "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/{reference}"
AWARD_NOTICE_URL_TEMPLATE = "https://canadabuys.canada.ca/en/tender-opportunities/award-notice/{reference}"

# UNSPSC segment(s) treated as automatically in-scope regardless of keyword
# match. Segment 46 is "Defense and Law Enforcement and Security and Safety
# Equipment and Supplies" in the UNSPSC taxonomy.
RELEVANT_UNSPSC_SEGMENTS = {"46"}

REQUEST_TIMEOUT_SECONDS = 60
