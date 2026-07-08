import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

# Your `sources` table has one row per CanadaBuys feed rather than a single
# shared row, so tender notices and award notices are attributed to
# different source_ids. Override via env vars if these rows are ever
# recreated with new ids.
TENDER_SOURCE_ID = os.environ.get("TENDER_SOURCE_ID", "5ff27bde-7c78-4a5a-8efe-a0be8ef84fc8")
AWARD_SOURCE_ID = os.environ.get("AWARD_SOURCE_ID", "0bce66c4-a58c-48b5-aede-6ae2b85ae890")

# CanadaBuys publishes federal procurement notices only.
JURISDICTION = "Federal"

KEYWORDS_FILE = os.environ.get(
    "KEYWORDS_FILE",
    os.path.join(os.path.dirname(__file__), "..", "config", "keywords.txt"),
)

# Open data CSV endpoints (refreshed by PSPC most mornings before 8:30am ET).
NEW_TENDER_NOTICES_URL = (
    "https://canadabuys.canada.ca/opendata/pub/"
    "newTenderNotice-nouvelAvisAppelOffres.csv"
)
# Current fiscal-year award notices file. PSPC republishes this under a
# fiscal-year-specific name each April; if the collector logs a 404 for this
# URL, check https://canadabuys.canada.ca/en/procurement-and-contracting-data
# for the current filename and update this constant.
AWARD_NOTICES_URL = (
    "https://canadabuys.canada.ca/opendata/pub/"
    "awardNotice-avisAttribution.csv"
)

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
