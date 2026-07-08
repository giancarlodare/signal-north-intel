import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

# Name of the row in the `sources` table that represents CanadaBuys.
# Override with the SOURCE_NAME env var if your sources.name value differs.
SOURCE_NAME = os.environ.get("SOURCE_NAME", "CanadaBuys")

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
