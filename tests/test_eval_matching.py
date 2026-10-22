"""Tests for eval matching and metrics. Issues are built by hand; no model is called."""

import json

import pytest

from evals import run_eval
from evals.matching import Label, Reported, Run, score_file, total
from code_reviewer.pipeline import ReviewRun
from code_reviewer.schemas import ReviewResult
from code_reviewer.tools import files

BUG = Label("a.py#0", "bug", (10,))
OTHER_BUG = Label("a.py#1", "bug", (12,))


def bug(line, verification="confirmed", title="t"):
    return Reported(line, "bug", verification, title)


def score(issues, labels=(BUG,)):
    return score_file("a.py", [Run("a.py", issues)], list(labels))


# --- The ±1 rule ---

def test_issue_one_line_away_matches():
    result = score([bug(11)])
    assert result.levels["all"].recall == 1
    assert result.levels["all"].precision == 1


def test_issue_two_lines_away_is_a_false_positive():
    result = score([bug(12)])
    assert result.levels["all"].recall == 0
    assert result.levels["all"].false_positives == 1


def test_any_line_of_the_label_counts():
    label = Label("a.py#0", "bug", (6, 13))
    assert score([bug(14)], [label]).levels["all"].found == 1


# --- Not one-to-one ---

def test_second_issue_on_the_same_label_is_a_duplicate():
    result = score([bug(10), bug(11)])
    assert result.duplicates == 1
    assert result.levels["all"].found == 1  # the label is found once
    assert result.levels["all"].correct == 2  # both reports are correct


def test_issue_matching_two_labels_counts_for_both():
    result = score([bug(11)], [BUG, OTHER_BUG])
    assert result.levels["all"].found == 2
    assert result.levels["all"].correct == 1
    assert result.duplicates == 0


# --- Clean file and levels ---

def test_every_bug_on_a_clean_file_is_a_false_positive():
    result = score([bug(3), bug(7)], labels=())
    assert result.levels["all"].false_positives == 2
    assert [issue.line for issue in result.false_positive_issues] == [3, 7]
    assert result.levels["all"].precision == 0
    assert result.levels["all"].recall is None  # nothing to find, not 0%


def test_levels_filter_by_verification():
    result = score([bug(10, "crashed")])
    assert result.levels["all"].recall == 1
    assert result.levels["confirmed"].recall == 0
    assert result.levels["confirmed"].precision is None  # no confirmed reports at all
    assert result.levels["confirmed+crashed"].recall == 1


# --- Categories ---

def test_readability_issue_next_to_a_bug_is_other_not_miscategorized():
    # Like cache.py: a note about utcnow() on line 18, next to the bug on line 19.
    note = Reported(9, "readability", "not_tested", "utcnow() is deprecated")
    result = score([note])
    assert result.miscategorized == []
    assert result.other == 1
    assert result.levels["all"].found == 0


def test_bug_issue_on_a_performance_line_is_only_miscategorized():
    slow = Label("a.py#0", "performance", (20,))
    result = score([bug(20)], [slow])
    assert len(result.miscategorized) == 1
    assert result.levels["all"].false_positives == 0


def test_bug_report_on_dead_code_is_miscategorized_not_a_false_positive():
    # palindrome.py line 22: unreachable code the model reported as a bug.
    dead = Label("a.py#1", "readability", (22,))
    result = score([bug(16), bug(22)], [Label("a.py#0", "bug", (16,)), dead])
    assert [issue.line for issue in result.miscategorized] == [22]
    assert result.levels["all"].false_positives == 0
    assert result.levels["all"].precision == 1


def test_readability_label_is_tracked_but_not_scored():
    dead = Label("a.py#1", "readability", (22,))
    result = score([Reported(22, "readability", "not_tested")], [BUG, dead])
    assert result.label_hits["a.py#1"] == [["not_tested"]]
    assert result.levels["all"].expected == 1  # only the bug label is scored


def test_readability_issue_away_from_labels_is_counted_as_other():
    result = score([Reported(30, "readability", "not_tested")])
    assert result.other == 1
    assert result.miscategorized == []


def test_unmatched_performance_issue_is_counted():
    result = score([Reported(30, "performance", "not_tested")])
    assert result.unmatched_performance == 1


# --- Runs ---

def test_failed_run_is_excluded_from_metrics():
    runs = [Run("a.py", [bug(10)]), Run("a.py", None, "APIError: overloaded")]
    result = score_file("a.py", runs, [BUG])
    assert result.failed == 1
    assert result.runs == 1
    assert result.levels["all"].expected == 1
    assert result.levels["all"].recall == 1


def test_label_hits_record_statuses_per_run():
    runs = [Run("a.py", [bug(10, "confirmed")]), Run("a.py", [])]
    result = score_file("a.py", runs, [BUG])
    assert result.label_hits["a.py#0"] == [["confirmed"], []]


def test_total_pools_counts_instead_of_averaging():
    one_label = score_file("a.py", [Run("a.py", [bug(10)])], [BUG])
    two_labels = score_file("b.py", [Run("b.py", [])], [BUG, OTHER_BUG])
    pooled = total([one_label, two_labels])
    # Average of 100% and 0% would be 50%. Pooled: 1 found of 3 labels.
    assert pooled.levels["all"].found == 1
    assert pooled.levels["all"].expected == 3


# --- Isolation ---

def test_isolated_repo_hides_other_files(tmp_path):
    source = tmp_path / "dataset" / "a.py"
    source.parent.mkdir()
    source.write_text("x = 1\n")
    (tmp_path / "labels.json").write_text("{}")
    original = files.PROJECT_ROOT

    with run_eval.isolated_repo(source) as name:
        assert files.resolve_repo_path(name) is not None
        assert files.resolve_repo_path("../labels.json") is None
        assert files.resolve_repo_path(str(tmp_path / "labels.json")) is None

    assert files.PROJECT_ROOT == original


def test_failed_run_is_recorded(monkeypatch, tmp_path):
    def broken_review(file_path):
        raise RuntimeError("model returned invalid output")

    monkeypatch.setattr(run_eval, "review_file", broken_review)
    source = tmp_path / "a.py"
    source.write_text("x = 1\n")

    record = run_eval.run_once(source)

    assert record["issues"] is None
    assert record["error"] == "RuntimeError: model returned invalid output"
    assert run_eval.to_run(record).issues is None


def test_stopped_eval_keeps_the_runs_that_finished(monkeypatch, tmp_path):
    calls = []

    def review_then_stop(file_path):
        calls.append(file_path)
        if len(calls) == 2:
            raise KeyboardInterrupt  # like pressing Ctrl+C during the second run
        return ReviewRun(ReviewResult(issues=[]), [])

    monkeypatch.setattr(run_eval, "review_file", review_then_stop)
    source = tmp_path / "a.py"
    source.write_text("x = 1\n")
    path = tmp_path / "result.json"
    result = {"complete": False, "runs": []}

    with pytest.raises(KeyboardInterrupt):
        run_eval.run_all([source], result, path)

    saved = json.loads(path.read_text())
    assert len(saved["runs"]) == 1
    assert saved["complete"] is False
