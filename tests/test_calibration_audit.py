"""Tests for the Phase 5 calibration audit: stratified sampling (representation,
shortfall honesty, seed reproducibility), the blind-match pairing, the
agreement comparison (exact headline, within-one secondary, boundary flips),
report rendering, and the structural report-only rule (write-verb grep)."""
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import calibration_audit as ca


def _sig(sid, grade=3, materiality=3, stype="procurement_intent",
         confidence="probable", title="Peel tenders SCADA integration",
         quote="the region will issue a tender for SCADA integration",
         doc_id="d1"):
    return {"id": sid, "evidence_grade": grade, "materiality": materiality,
            "signal_type": stype, "confidence": confidence, "title": title,
            "quote_or_line": quote, "document_id": doc_id,
            "extracted_by": "extraction@v1",
            "organizations": {"canonical_name": "Region of Peel"}}


# --- report-only, enforced structurally --------------------------------------
def test_module_source_contains_no_database_write_verbs():
    # The hard rule: no audit result may modify a signal, a score, or a
    # threshold. The module must have NO database write path; this grep makes
    # a regression to auto-correction fail loudly in CI.
    src = Path(ca.__file__).read_text(encoding="utf-8")
    forbidden = ("insert_", "update_", "delete_", "_request(",
                 "requests.post", "requests.patch", "requests.delete",
                 '"POST"', "'POST'", '"PATCH"', "'PATCH'", '"DELETE"', "'DELETE'")
    hits = [v for v in forbidden if v in src]
    assert hits == [], f"write verbs found in calibration_audit.py: {hits}"


# --- stratified sampling ------------------------------------------------------
def test_sample_represents_high_grades_and_reports_shortfall_never_pads():
    signals = ([_sig(f"g1-{i}", grade=1) for i in range(20)]
               + [_sig(f"g2-{i}", grade=2) for i in range(20)]
               + [_sig(f"g3-{i}", grade=3) for i in range(8)]
               + [_sig(f"g4-{i}", grade=4) for i in range(6)]
               + [_sig(f"g5-{i}", grade=5) for i in range(2)])   # thin stratum
    sample, shortfalls = ca.stratified_sample(signals, per_grade=6, seed="2026-07")
    by_grade = {}
    for s in sample:
        by_grade[s["evidence_grade"]] = by_grade.get(s["evidence_grade"], 0) + 1
    assert by_grade == {1: 6, 2: 6, 3: 6, 4: 6, 5: 2}   # all of grade 5, no padding
    assert shortfalls == {5: 4}
    assert len(sample) == 26


def test_sample_is_reproducible_for_the_same_seed():
    signals = [_sig(f"s{i}", grade=1 + i % 5) for i in range(60)]
    a, _ = ca.stratified_sample(signals, seed="2026-07")
    b, _ = ca.stratified_sample(signals, seed="2026-07")
    c, _ = ca.stratified_sample(signals, seed="2026-08")
    assert [s["id"] for s in a] == [s["id"] for s in b]
    assert [s["id"] for s in a] != [s["id"] for s in c]


# --- blind-match pairing ------------------------------------------------------
def test_match_pairs_on_quote_overlap_and_falls_back_to_title():
    original = _sig("x", quote="the region will issue a tender for SCADA integration")
    by_quote = {"title": "different words entirely",
                "quote_or_line": "region will issue a tender for SCADA integration works"}
    noise = {"title": "unrelated grant program", "quote_or_line": "totally other text here"}
    matched, score = ca.match_reextracted(original, [noise, by_quote])
    assert matched is by_quote and score >= ca.MATCH_THRESHOLD

    by_title = {"title": "Peel tenders SCADA integration", "quote_or_line": ""}
    matched, _ = ca.match_reextracted(original, [noise, by_title])
    assert matched is by_title


def test_no_match_below_threshold_is_not_reproduced():
    original = _sig("x")
    matched, score = ca.match_reextracted(
        original, [{"title": "zzz", "quote_or_line": "qqq www eee"}])
    assert matched is None and score == 0.0
    rec = ca.compare(original, None, "tender_notice")
    assert rec["matched"] is False
    assert rec["category"] == "not_reproduced"


# --- comparison: exact headline, within-one secondary, boundary flips ---------
def test_compare_exact_agreement():
    original = _sig("x", materiality=4)
    rec = ca.compare(original, {"materiality": 4, "signal_type": "procurement_intent",
                                "confidence": "probable"}, "tender_notice")
    assert rec["category"] == "agree"
    assert rec["materiality"]["exact"] and rec["materiality"]["within_one"]
    assert rec["materiality"]["boundary_crossings"] == []


def test_boundary_crossing_flags_the_flips_that_change_the_brief():
    # 4 -> 3 crosses the lens bar (draft changes); 3 -> 2 crosses the brief
    # bar; 5 -> 4 crosses nothing a reader sees. All are within-one.
    def flip(orig, new):
        rec = ca.compare(_sig("x", materiality=orig),
                         {"materiality": new, "signal_type": "procurement_intent",
                          "confidence": "probable"}, "tender_notice")
        return rec["materiality"]
    m = flip(4, 3)
    assert not m["exact"] and m["within_one"]
    assert m["boundary_crossings"] == [ca.LENS_MIN_MATERIALITY]
    m = flip(3, 2)
    assert m["boundary_crossings"] == [ca.RECENT_MIN_MATERIALITY]
    m = flip(5, 4)
    assert m["boundary_crossings"] == []
    m = flip(5, 2)   # category error: crosses both bars, not within one
    assert not m["within_one"]
    assert m["boundary_crossings"] == [ca.RECENT_MIN_MATERIALITY, ca.LENS_MIN_MATERIALITY]


def test_signal_type_flip_reports_derived_grade_consequence():
    original = _sig("x", stype="procurement_intent")
    rec = ca.compare(original, {"materiality": 3, "signal_type": "other",
                                "confidence": "probable"}, "tender_notice")
    assert rec["signal_type"]["exact"] is False
    assert "grade_equal" in rec["signal_type"]   # derived, reported alongside
    assert rec["category"] == "field_mismatch"


# --- report rendering ---------------------------------------------------------
def _meta(**over):
    meta = {"month": "2026-07", "model": "claude-opus-4-8", "reason": "",
            "eligible": 120, "per_grade": 6, "shortfalls": {5: 4},
            "unfetchable": 1, "prompt_versions": {"extraction@v1"}}
    meta.update(over)
    return meta


def test_report_lists_every_disagreement_with_both_scores():
    agree = ca.compare(_sig("a", materiality=3),
                       {"materiality": 3, "signal_type": "procurement_intent",
                        "confidence": "probable"}, "tender_notice")
    flip = ca.compare(_sig("b", materiality=4, title="Lens item"),
                      {"materiality": 3, "signal_type": "procurement_intent",
                       "confidence": "probable"}, "tender_notice")
    gone = ca.compare(_sig("c", title="Vanished signal"), None, "tender_notice")
    for r in (agree, flip, gone):
        r.update({"buyer": "Region of Peel", "doc_type": "tender_notice",
                  "doc_url": "https://example.gov/x"})
    report = ca.render_report([agree, flip, gone], _meta())
    assert "Disagreements to adjudicate (2)" in report
    assert "4 vs re-scored 3" in report            # both scores shown
    assert "CROSSES boundary 4" in report          # lens-bar flip flagged
    assert "NOT REPRODUCED" in report              # first-class category
    assert "short by 4" in report                  # thin stratum stated
    assert "excluded: source document" in report   # unfetchable counted
    assert "REPORT-ONLY" in report                 # the rule restated in the report
    assert "—" not in report                       # no em dashes, ever


def test_report_handles_a_fully_agreeing_month():
    agree = ca.compare(_sig("a"), {"materiality": 3,
                                   "signal_type": "procurement_intent",
                                   "confidence": "probable"}, "tender_notice")
    agree.update({"buyer": None, "doc_type": "tender_notice", "doc_url": None})
    report = ca.render_report([agree], _meta(shortfalls={}, unfetchable=0))
    assert "Disagreements to adjudicate (0)" in report
    assert "None." in report


# --- run(): dry-run honesty and report files ----------------------------------
def test_dry_run_samples_but_never_calls_the_llm_or_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(ca.supabase_client, "fetch_all_rows_where",
                        lambda *a, **k: [_sig(f"s{i}", grade=1 + i % 5) for i in range(40)])

    def boom(*a, **k):
        raise AssertionError("dry-run must not re-score or fetch documents")
    monkeypatch.setattr(ca, "extract_signals", boom)
    monkeypatch.setattr(ca.supabase_client, "fetch_rows_where", boom)

    result = ca.run(dry_run=True, today=date(2026, 7, 20), out_dir=str(tmp_path))
    assert result["dry_run"] is True and result["sampled"] == 30
    assert list(tmp_path.iterdir()) == []   # nothing written


def test_full_run_writes_report_and_json(monkeypatch, tmp_path):
    signals = [_sig(f"s{i}", grade=1 + i % 5, doc_id=f"d{i}") for i in range(10)]
    monkeypatch.setattr(ca.supabase_client, "fetch_all_rows_where",
                        lambda *a, **k: signals)
    monkeypatch.setattr(ca.supabase_client, "fetch_rows_where",
                        lambda table, select, filters, limit=1: [{
                            "id": filters["id"][3:], "title": "Doc", "doc_type": "tender_notice",
                            "url": "https://example.gov/x", "published_on": "2026-07-01",
                            "source_id": "src1", "content": "body text"}])
    monkeypatch.setattr(ca.supabase_client, "get_source_name", lambda sid: "Src")
    # Blind re-score agrees on everything except one field for signal s3.
    def fake_extract(doc, source_name, model):
        return ([{"title": "Peel tenders SCADA integration",
                  "quote_or_line": "the region will issue a tender for SCADA integration",
                  "materiality": 3, "signal_type": "procurement_intent",
                  "confidence": "probable"}], "extraction@v1")
    monkeypatch.setattr(ca, "extract_signals", fake_extract)

    result = ca.run(dry_run=False, today=date(2026, 7, 20), out_dir=str(tmp_path))
    assert result["compared"] == 10 and result["dry_run"] is False
    report = (tmp_path / ca.REPORT_MD).read_text()
    assert "Calibration audit 2026-07" in report
    data = json.loads((tmp_path / ca.REPORT_JSON).read_text())
    assert len(data["records"]) == 10
    assert "—" not in report
