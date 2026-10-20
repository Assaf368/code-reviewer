"""Tests for verify_issue: how a reported bug is classified after its test runs.

Each test plays the role of the model: it builds an Issue by hand and checks
that the verification step labels it correctly. No model is called.
"""

from code_reviewer.schemas import Issue
from code_reviewer.verification import verify_issue

# A tiny file with a known bug: add() subtracts instead of adding.
SOURCE = "def add(a, b):\n    return a - b\n"


def bug(test_code=None, untestable_reason=None):
    """Build a bug report as if the model had returned it."""
    return Issue(
        line=2,
        category="bug",
        severity="critical",
        title="t",
        explanation="e",
        fix="f",
        test_code=test_code,
        untestable_reason=untestable_reason,
    )


# --- The test runs and gives a clear answer ---

def test_failing_assert_confirms_the_bug():
    # add(2, 3) returns -1, so the assert fails: the bug is real.
    assert verify_issue(SOURCE, bug("assert add(2, 3) == 5")) == "confirmed"


def test_passing_assert_means_not_reproduced():
    # add(3, 2) happens to return 1, so this claim does not hold.
    assert verify_issue(SOURCE, bug("assert add(3, 2) == 1")) == "not_reproduced"


# --- The test could not run properly ---

def test_undefined_name_in_test_is_a_broken_test():
    # The test calls sub(), which does not exist in the file.
    assert verify_issue(SOURCE, bug("assert sub(1, 1) == 0")) == "test_error"


def test_syntax_error_in_test_is_a_broken_test():
    assert verify_issue(SOURCE, bug("assert add(2, 3) ==")) == "test_error"


def test_assert_inside_source_is_inconclusive():
    # The AssertionError comes from the reviewed code, not from the test.
    # Before the fix, this case was wrongly marked as confirmed.
    source = "def f(x):\n    assert x > 0\n    return x\n"
    assert verify_issue(source, bug("assert f(-1) == -1")) == "inconclusive"


def test_exception_inside_source_is_crashed():
    # The reviewed code raises a non-assert exception: a crash is usually the bug itself.
    source = "def first(items):\n    return items[0]\n"
    assert verify_issue(source, bug("assert first([]) is None")) == "crashed"


def test_source_that_fails_to_load():
    # The reviewed file crashes as soon as it is imported.
    source = "raise RuntimeError('boom')\n"
    assert verify_issue(source, bug("assert True")) == "source_error"


def test_main_block_in_source_does_not_run():
    # Code under __main__ must not run during verification.
    source = SOURCE + "\nif __name__ == '__main__':\n    raise SystemExit('should not run')\n"
    assert verify_issue(source, bug("assert add(2, 3) == 5")) == "confirmed"


# --- No test was written ---

def test_bug_without_test_is_missing_test():
    assert verify_issue(SOURCE, bug()) == "missing_test"


def test_bug_with_untestable_reason_is_unverified():
    issue = bug(untestable_reason="Needs a live database connection")
    assert verify_issue(SOURCE, issue) == "unverified"


def test_test_code_wins_over_untestable_reason():
    # If both are given, running the test beats trusting the model.
    issue = bug("assert add(2, 3) == 5", untestable_reason="Needs a database")
    assert verify_issue(SOURCE, issue) == "confirmed"


def test_non_bug_issues_are_not_tested():
    issue = Issue(line=1, category="readability", severity="minor",
                  title="t", explanation="e", fix="f")
    assert verify_issue(SOURCE, issue) == "not_tested"


def test_source_names_do_not_clash_with_the_runner():
    # Regression: the runner once ran tests in its own namespace, so a function
    # named f, test or sys in the reviewed file was replaced by the runner's variables.
    source = "def f(x):\n    return x + 1\n\ndef test():\n    return 'ok'\n\nsys = 'mine'\n"
    test_code = "assert f(1) == 3\nassert test() == 'ok'\nassert sys == 'mine'"
    assert verify_issue(source, bug(test_code)) == "confirmed"