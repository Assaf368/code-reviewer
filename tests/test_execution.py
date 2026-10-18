"""Tests for the sandboxed runner: exit codes and the timeout."""

from code_reviewer.tools import execution
from code_reviewer.tools.execution import (
    SOURCE_ASSERTION_FAILED,
    SOURCE_FAILED_TO_LOAD,
    SOURCE_RAISED,
    TEST_ASSERTION_FAILED,
    TEST_PASSED,
    TEST_RAISED,
    execute_python,
    run_test,
)

SOURCE = "def double(x):\n    return x * 2\n"


def test_passing_test_exits_with_zero():
    assert run_test(SOURCE, "assert double(2) == 4").exit_code == TEST_PASSED


def test_failing_assert_in_test():
    assert run_test(SOURCE, "assert double(2) == 5").exit_code == TEST_ASSERTION_FAILED


def test_failing_assert_in_source():
    source = "def check(x):\n    assert x\n"
    assert run_test(source, "check(0)").exit_code == SOURCE_ASSERTION_FAILED


def test_exception_in_test():
    assert run_test(SOURCE, "missing()").exit_code == TEST_RAISED


def test_exception_in_source():
    source = "def boom():\n    return 1 / 0\n"
    assert run_test(source, "boom()").exit_code == SOURCE_RAISED


def test_source_that_fails_to_load():
    assert run_test("import not_a_real_module\n", "pass").exit_code == SOURCE_FAILED_TO_LOAD


def test_infinite_loop_times_out(monkeypatch):
    # Shorten the limit so the test suite stays fast.
    monkeypatch.setattr(execution, "TIMEOUT_SECONDS", 1)
    result = execute_python("while True:\n    pass\n")
    assert result.timed_out


def test_output_is_captured():
    result = execute_python("print('hello')")
    assert result.exit_code == 0
    assert result.stdout.strip() == "hello"