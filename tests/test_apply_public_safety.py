"""Tests for the independent member-read derivation pass
(src/apply_public_safety.py, operator 2026-07-27). The DB read/write is I/O;
here we prove compute(): it flags the right signals, treats defence as
public-safety, and is idempotent (no change when the stored flag already
matches)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.filters import Keywords
from src import apply_public_safety as ap

KW = Keywords(general=("police", "paramedic", "fire service"),
              defence=("armoured", "surveillance"))


def _sig(sid, title="t", org_type=None, defence=False, stored=False):
    return {"id": sid, "title": title, "public_safety": stored,
            "organizations": {"org_type": org_type},
            "documents": {"defence_relevant": defence}}


def test_org_type_signal_flagged_true():
    changes = ap.compute([_sig("a", org_type="police_service", stored=False)], KW)
    assert changes == [("a", True)]


def test_keyword_signal_flagged_true():
    changes = ap.compute([_sig("a", title="Police radio upgrade",
                               org_type="municipality", stored=False)], KW)
    assert changes == [("a", True)]


def test_defence_signal_is_public_safety():
    # defence is a public-safety subset; a defence_relevant signal flags true
    # even with a general org and neutral title.
    changes = ap.compute([_sig("a", title="generic works",
                               org_type="municipality", defence=True,
                               stored=False)], KW)
    assert changes == [("a", True)]


def test_general_signal_flagged_false_stays_false():
    # A general municipal signal already stored false needs no change.
    changes = ap.compute([_sig("a", title="watermain replacement",
                               org_type="municipality", stored=False)], KW)
    assert changes == []


def test_general_signal_wrongly_true_is_corrected_to_false():
    # Idempotency + self-healing: a general item stored true (e.g. a stale
    # value) is corrected down, keeping the fail-closed floor honest.
    changes = ap.compute([_sig("a", title="road resurfacing",
                               org_type="municipality", stored=True)], KW)
    assert changes == [("a", False)]


def test_public_safety_signal_already_true_is_noop():
    changes = ap.compute([_sig("a", org_type="police_service", stored=True)], KW)
    assert changes == []


def test_mixed_batch_reports_only_the_diffs():
    signals = [
        _sig("police_new", org_type="police_board", stored=False),   # -> True
        _sig("police_set", org_type="police_service", stored=True),  # noop
        _sig("general_ok", title="tree planting", org_type="municipality",
             stored=False),                                          # noop
        _sig("general_bad", title="SCADA integration", org_type="municipality",
             stored=True),                                           # -> False
    ]
    changes = dict(ap.compute(signals, KW))
    assert changes == {"police_new": True, "general_bad": False}


def test_list_shaped_embeds_are_handled():
    # PostgREST may return embedded resources as single-element lists.
    s = {"id": "a", "title": "consulting", "public_safety": False,
         "organizations": [{"org_type": "corrections"}],
         "documents": [{"defence_relevant": False}]}
    assert ap.compute([s], KW) == [("a", True)]
