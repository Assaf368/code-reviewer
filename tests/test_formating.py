"""Tests for the summary line, which is built in code from verified results."""

from code_reviewer.formatting import build_summary


def test_summary_counts_each_status():
    verifications = ["confirmed", "confirmed", "not_reproduced", "unverified", "not_tested"]

    summary = build_summary(verifications)

    assert summary == (
        "2 of 4 reported bugs confirmed, 1 not reproduced, "
        "1 need a manual check, 1 other issues."
    )


def test_summary_with_no_issues():
    assert build_summary([]) == (
        "0 of 0 reported bugs confirmed, 0 not reproduced, "
        "0 need a manual check, 0 other issues."
    )