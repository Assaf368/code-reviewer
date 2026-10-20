from typing import Literal

from code_reviewer.schemas import Issue
from code_reviewer.tools.execution import (
    SOURCE_ASSERTION_FAILED,
    SOURCE_FAILED_TO_LOAD,
    SOURCE_RAISED,
    TEST_ASSERTION_FAILED,
    TEST_PASSED,
    run_test,
)

Verification = Literal[
    "confirmed",
    "not_reproduced",
    "crashed",
    "inconclusive",
    "test_error",
    "source_error",
    "unverified",
    "missing_test",
    "not_tested",
]


def verify_issue(source: str, issue: Issue) -> Verification:
    """Run the issue's test against the source and classify the result."""
    if issue.category != "bug":
        return "not_tested"
    if not issue.test_code:
        return "unverified" if issue.untestable_reason else "missing_test"

    result = run_test(source, issue.test_code)

    if result.timed_out:
        return "test_error"
    if result.exit_code == TEST_ASSERTION_FAILED:
        return "confirmed"
    if result.exit_code == TEST_PASSED:
        return "not_reproduced"
    if result.exit_code == SOURCE_FAILED_TO_LOAD:
        return "source_error"
    if result.exit_code == SOURCE_RAISED:
        return "crashed"
    if result.exit_code == SOURCE_ASSERTION_FAILED:
        return "inconclusive"
    return "test_error"