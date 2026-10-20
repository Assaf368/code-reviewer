from types import CodeType
from typing import Literal

from code_reviewer.schemas import Issue
from code_reviewer.tools.execution import (
    SOURCE_ASSERTION_FAILED,
    SOURCE_FAILED_TO_LOAD,
    SOURCE_RAISED,
    TEST_ASSERTION_FAILED,
    TEST_PASSED,
    ExecutionResult,
    run_test,
)

Verification = Literal[
    "confirmed",
    "not_reproduced",
    "crashed",
    "inconclusive",
    "line_not_reached",
    "test_error",
    "source_error",
    "unverified",
    "missing_test",
    "not_tested",
]


def code_lines(source: str) -> set[int]:
    """Line numbers that hold code. Lines like `else:` or comments hold none."""
    lines = set()
    pending = [compile(source, "target.py", "exec")]
    while pending:
        code = pending.pop()
        lines.update(line for _, _, line in code.co_lines() if line is not None)
        pending.extend(const for const in code.co_consts if isinstance(const, CodeType))
    return lines


def line_reached(source: str, line: int, executed: set[int]) -> bool:
    """Did the reported line run? A line without code counts if a neighbor ran."""
    if line in executed:
        return True
    if line in code_lines(source):
        return False
    return bool({line - 1, line + 1} & executed)


def classify(result: ExecutionResult) -> Verification:
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


def verify_issue(source: str, issue: Issue) -> Verification:
    """Run the issue's test against the source and classify the result."""
    if issue.category != "bug":
        return "not_tested"
    if not issue.test_code:
        return "unverified" if issue.untestable_reason else "missing_test"

    result = run_test(source, issue.test_code)
    verification = classify(result)

    # A failure proves the reported line only if that line actually ran.
    if (
        verification in ("confirmed", "crashed")
        and result.executed_lines is not None
        and not line_reached(source, issue.line, result.executed_lines)
    ):
        return "line_not_reached"
    return verification
