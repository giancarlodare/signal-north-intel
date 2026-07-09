import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import config


def _award_url(fiscal_year: str) -> str:
    return (
        "https://canadabuys.canada.ca/opendata/pub/"
        f"{fiscal_year}-awardNotice-avisAttribution.csv"
    )


def test_outside_grace_returns_only_current_fiscal_year():
    # Mid-January: fiscal year 2025-2026 is current, no rollover nearby.
    urls = config.award_notice_urls(date(2026, 1, 15))
    assert urls == [_award_url("2025-2026")]


def test_just_before_rollover_returns_only_current():
    # March 20 is still fiscal year 2025-2026; the rollover hasn't happened.
    urls = config.award_notice_urls(date(2026, 3, 20))
    assert urls == [_award_url("2025-2026")]


def test_just_after_rollover_includes_previous_fiscal_year():
    # April 15 is inside the grace window: current 2026-2027 plus previous
    # 2025-2026 so late-posted prior-year awards are still collected.
    urls = config.award_notice_urls(date(2026, 4, 15))
    assert urls == [_award_url("2026-2027"), _award_url("2025-2026")]


def test_on_rollover_day_includes_previous_fiscal_year():
    urls = config.award_notice_urls(date(2026, 4, 1))
    assert urls == [_award_url("2026-2027"), _award_url("2025-2026")]


def test_beyond_grace_window_drops_previous_fiscal_year():
    # 60-day default grace: by mid-July the previous year's file is dropped.
    urls = config.award_notice_urls(date(2026, 7, 15))
    assert urls == [_award_url("2026-2027")]
