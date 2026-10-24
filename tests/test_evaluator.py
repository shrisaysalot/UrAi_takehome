"""
Evaluator Self-Tests.
Tests that corrupt a copy of the ground truth:
1. Drop a row -> flags dropped row, recall reduction
2. Merge two rows -> flags diagnostic merge / row reduction
3. Swap two digits in a number -> flags cell raw extraction & value mismatch
4. Change a label slightly -> flags fuzzy match and exact label accuracy drop
5. Ambiguous / misplaced repeated label -> flags unresolved or alignment cost increase
6. Page-level gate triggers on empty rows or column count mismatch
"""

import copy
import json
import pytest
from eval.aligner import RowAligner
from eval.scorer import TableScorer


@pytest.fixture
def ground_truth():
    with open("data/ground_truth_v0.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_evaluator_perfect_match(ground_truth):
    scorer = TableScorer()
    res = scorer.score(ground_truth, ground_truth)
    assert res["page_level_gate"] == "PASSED"
    assert res["alignment"]["row_recall"] == 1.0
    assert res["alignment"]["row_precision"] == 1.0
    assert res["alignment"]["exact_label_accuracy"] == 1.0
    assert res["alignment"]["dropped"] == 0
    assert res["alignment"]["unresolved"] == 0
    assert res["extraction"]["cell_raw_accuracy"] == 1.0
    assert res["parsing"]["parsing_accuracy"] == 1.0
    assert res["structure"]["header_vs_item_accuracy"] == 1.0
    assert res["structure"]["subtotal_total_accuracy"] == 1.0
    assert res["structure"]["parent_accuracy"] == 1.0
    assert res["invariants"]["all_passed"] is True


def test_evaluator_drop_row(ground_truth):
    corrupt = copy.deepcopy(ground_truth)
    # Drop row 5 ("電子記録債権")
    dropped_row = corrupt["tables"][0]["rows"].pop(5)
    
    scorer = TableScorer()
    res = scorer.score(ground_truth, corrupt)
    
    assert res["page_level_gate"] == "PASSED"
    # Evaluator MUST flag dropped row
    assert res["alignment"]["dropped"] == 1
    assert res["alignment"]["row_recall"] < 1.0
    # Denominator for extraction is all GT cells -> raw accuracy must drop
    assert res["extraction"]["cell_raw_accuracy"] < 1.0


def test_evaluator_merge_two_rows(ground_truth):
    corrupt = copy.deepcopy(ground_truth)
    rows = corrupt["tables"][0]["rows"]
    # Merge row 3 ("受取手形") and row 4 ("売掛金")
    merged_label = rows[3]["label_raw"] + rows[4]["label_raw"]
    rows[3]["label_raw"] = merged_label
    rows.pop(4)
    
    scorer = TableScorer()
    res = scorer.score(ground_truth, corrupt)
    
    # Must detect merge in diagnostics
    merges = res["alignment"]["diagnostics"]["merges"]
    assert len(merges) >= 1
    assert any(m["pred_label"] == "受取手形売掛金" for m in merges)


def test_evaluator_swap_digits_in_number(ground_truth):
    corrupt = copy.deepcopy(ground_truth)
    # Row 2 is "現金及び預金", c1 is "2,002,429" (2002429)
    # Swap last two digits: "2,002,492" (2002492)
    row2_c1 = corrupt["tables"][0]["rows"][2]["cells"]["c1"]
    row2_c1["raw"] = "2,002,492"
    row2_c1["value_in_unit"] = 2002492
    
    scorer = TableScorer(tolerance_per_term=1)
    res = scorer.score(ground_truth, corrupt)
    
    # Raw match must fail for this cell
    assert res["extraction"]["raw_matched_cells"] == res["extraction"]["total_gt_cells"] - 1
    assert res["extraction"]["cell_raw_accuracy"] < 1.0
    # Invariant for 流動資産合計 will detect the 63 unit discrepancy!
    assert res["invariants"]["all_passed"] is False


def test_evaluator_change_label_slightly(ground_truth):
    corrupt = copy.deepcopy(ground_truth)
    # Change "現金及び預金" to "現金及び預入金" (near miss fuzzy match)
    corrupt["tables"][0]["rows"][2]["label_raw"] = "現金及び預入金"
    
    scorer = TableScorer()
    res = scorer.score(ground_truth, corrupt)
    
    # Exact label accuracy must drop, fuzzy must be >= 1
    assert res["alignment"]["fuzzy"] >= 1
    assert res["alignment"]["exact_label_accuracy"] < 1.0
    # But row recall should remain 1.0 since it's a confirmed fuzzy match
    assert res["alignment"]["row_recall"] == 1.0


def test_evaluator_unresolved_tie_or_misplaced_label(ground_truth):
    corrupt = copy.deepcopy(ground_truth)
    # In row 10 ("その他" under 流動資産), duplicate another "その他" in the exact same section
    # creating ambiguous identical candidates
    extra_other = copy.deepcopy(corrupt["tables"][0]["rows"][10])
    corrupt["tables"][0]["rows"].insert(11, extra_other)
    
    scorer = TableScorer()
    res = scorer.score(ground_truth, corrupt)
    # Evaluator must flag an inserted row or unresolved match
    assert res["alignment"]["inserted"] >= 1 or res["alignment"]["unresolved"] >= 1


def test_evaluator_page_level_gate_empty_rows(ground_truth):
    corrupt = copy.deepcopy(ground_truth)
    corrupt["tables"][0]["rows"] = []
    
    scorer = TableScorer()
    res = scorer.score(ground_truth, corrupt)
    assert res["page_level_gate"] == "FAILED"
    assert "0 rows" in res["failure_reason"]


def test_evaluator_page_level_gate_column_mismatch(ground_truth):
    corrupt = copy.deepcopy(ground_truth)
    # Corrupt column count
    corrupt["tables"][0]["columns"].pop()
    
    scorer = TableScorer()
    res = scorer.score(ground_truth, corrupt)
    assert res["page_level_gate"] == "FAILED"
    assert "Column count mismatch" in res["failure_reason"]
