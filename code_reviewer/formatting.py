from collections import Counter

from code_reviewer.schemas import ReviewResult
from code_reviewer.verification import Verification

SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2}

MARKS = {
    "confirmed": " ✓ confirmed",
    "not_reproduced": " ✗ not reproduced",
    "crashed": " ! crashes",
    "inconclusive": " ? inconclusive",
    "line_not_reached": " ? reported line never ran",
    "test_error": " ⚠ broken test",
    "source_error": " ⚠ file failed to load",
    "unverified": " · needs manual check",
    "missing_test": " ⚠ no test",
    "not_tested": "",
}


def build_summary(verifications: list[Verification]) -> str:
    counts = Counter(verifications)
    bugs = len(verifications) - counts["not_tested"]
    return (
        f"{counts['confirmed']} of {bugs} reported bugs confirmed, "
        f"{counts['crashed']} crashed, "
        f"{counts['not_reproduced']} not reproduced, "
        f"{counts['unverified']} need a manual check, "
        f"{counts['not_tested']} other issues."
    )


def print_issue(issue, verification: Verification) -> None:
    print(f"[{issue.severity.upper()}] line {issue.line} · {issue.category} · "
          f"{issue.title}{MARKS[verification]}")
    print(f"    {issue.explanation}")
    if issue.test_code:
        print(f"    Test: {issue.test_code}")
    if issue.untestable_reason and not issue.test_code:
        print(f"    Why no test: {issue.untestable_reason}")
    print(f"    Fix: {issue.fix}\n")


def print_review(review: ReviewResult, verifications: list[Verification]) -> None:
    pairs = sorted(
        zip(review.issues, verifications),
        key=lambda pair: SEVERITY_ORDER[pair[0].severity],
    )
    shown = [p for p in pairs if p[1] != "not_reproduced"]
    rejected = [p for p in pairs if p[1] == "not_reproduced"]

    print(f"\n{build_summary(verifications)}\n")
    for issue, verification in shown:
        print_issue(issue, verification)

    if rejected:
        print("--- Claims that did not reproduce (likely false positives) ---\n")
        for issue, verification in rejected:
            print_issue(issue, verification)