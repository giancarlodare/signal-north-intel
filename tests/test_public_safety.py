"""Tests for the public-safety relevance predicate
(docs/public-safety-relevance-filter-design.md, operator 2026-07-27).

The truth-condition for the vertical-depth claim: a regional-government feed
mixes police/fire/EMS/corrections tenders with general municipal procurement,
and only the public-safety slice may reach the member. These tests pin the two
determination paths (resolved end-user org_type; keyword/facility fallback) and
the precision-over-recall stance (a watermain must NOT pass)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.filters import Keywords
from src import public_safety as ps

# A minimal keyword set standing in for config/keywords.txt so the tests do not
# depend on the live config's exact contents. Lowercased, substring-matched.
KW = Keywords(general=("police", "fire service", "paramedic", "corrections"),
              defence=("armoured", "surveillance"))


# --- Path 1: resolved end-user org_type (primary) ----------------------------
def test_public_safety_org_type_passes_regardless_of_text():
    # A generic construction title still passes when the resolved end-user is a
    # police/corrections org: the org resolver caught the end-user.
    assert ps.is_public_safety("police_service", "General renovation works", KW)
    assert ps.is_public_safety("police_board", "Consulting services", KW)
    assert ps.is_public_safety("corrections", "HVAC upgrade", KW)


def test_general_org_type_falls_through_to_text():
    # A multi-purpose buyer alone is never enough: the item's own text decides.
    assert not ps.is_public_safety("municipality", "watermain replacement", KW)
    assert not ps.is_public_safety("provincial_ministry", "road resurfacing", KW)


# --- Path 2: keyword/facility fallback (secondary) ---------------------------
def test_keyword_fallback_catches_public_safety_text_under_general_buyer():
    # Region-of-Peel-style feed: general buyer, but the title names a service.
    assert ps.is_public_safety("municipality", "Police radio system upgrade", KW)
    assert ps.is_public_safety("municipality", "Paramedic response vehicles", KW)


def test_defence_keyword_also_counts_as_public_safety():
    # defence is a public-safety subset (dual-use), so a defence term qualifies.
    assert ps.is_public_safety("municipality", "Armoured vehicle procurement", KW)


def test_facility_patterns_catch_construction_for_police():
    # The hard case: a generic construction tender is relevant only via its
    # public-safety facility end-user. These markers carry it.
    assert ps.is_public_safety(None, "12 Division renovation", KW)
    assert ps.is_public_safety(None, "22 Division roof replacement", KW)
    assert ps.is_public_safety("municipality", "New detention centre HVAC", KW)
    assert ps.is_public_safety("municipality", "Fire hall electrical retrofit", KW)
    assert ps.is_public_safety("municipality", "Fire station 5 generator", KW)
    assert ps.is_public_safety("municipality", "Paramedic station addition", KW)


def test_description_is_searched_too():
    assert ps.is_public_safety("municipality", "Facility upgrade",
                               KW, description="serving the local fire station")


# --- Precision over recall: the general slice must NOT leak ------------------
def test_general_municipal_items_do_not_pass():
    # Every one of these is the general slice a regional feed also carries; none
    # may reach the public-safety member view.
    for title in ["Watermain replacement, Derry Road",
                  "Road resurfacing program 2026",
                  "Long-term care facility food supply",
                  "SCADA system integration",
                  "Flow meter calibration services"]:
        assert not ps.is_public_safety("municipality", title, KW), title


def test_near_miss_terms_do_not_false_positive():
    # The design calls these out explicitly as non-policing look-alikes.
    assert not ps.is_public_safety("municipality", "Community safety zone signage", KW)
    assert not ps.is_public_safety("municipality", "Fireproofing coating supply", KW)


def test_unresolved_org_with_general_text_is_not_public_safety():
    assert not ps.is_public_safety(None, "Office furniture supply", KW)


# --- cluster_is_public_safety: ANY relevant member carries the cluster --------
def test_cluster_relevant_if_any_member_is():
    members = [
        {"title": "watermain replacement", "org_type": "municipality"},
        {"title": "12 Division renovation", "org_type": "municipality"},
    ]
    assert ps.cluster_is_public_safety(members, KW)


def test_cluster_not_relevant_when_all_general():
    members = [
        {"title": "watermain replacement", "org_type": "municipality"},
        {"title": "road resurfacing", "org_type": "municipality"},
    ]
    assert not ps.cluster_is_public_safety(members, KW)


def test_cluster_defence_member_carries_it():
    members = [{"title": "generic works", "org_type": "municipality",
                "defence_relevant": True}]
    assert ps.cluster_is_public_safety(members, KW)


def test_cluster_member_org_type_carries_it():
    members = [{"title": "consulting services", "org_type": "police_service"}]
    assert ps.cluster_is_public_safety(members, KW)


def test_cluster_missing_fields_degrade_safely():
    # Missing title/org_type must not raise; a bare, unresolvable member is not
    # public-safety (precision over recall).
    assert not ps.cluster_is_public_safety([{}], KW)


def test_keyword_matching_is_whole_word_not_substring():
    # The Bendix lesson (2026-07-27): 'ems' must not match 'Systems', and the
    # same for any keyword embedded in a longer word. Real whole-word uses of
    # the same keywords still pass.
    assert not ps.is_public_safety(
        "municipality",
        "Ottawa Transit Services RFSO for Bendix Air Brake Systems and Components",
        KW)
    assert ps.is_public_safety("municipality", "EMS station generator", KW)
    assert not ps.is_public_safety("municipality", "Air brake systems supply", KW)
