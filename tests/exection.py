import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from langchain.tools import tool

from code_reviewer.tools.files import resolve_repo_path

TIMEOUT_SECONDS = 5
MAX_OUTPUT_CHARS = 2000

# Exit codes of the test runner
TEST_PASSED = 0
TEST_ASSERTION_FAILED = 3
SOURCE_ASSERTION_FAILED = 4
SOURCE_FAILED_TO_LOAD = 5
TEST_RAISED = 6
SOURCE_RAISED = 7

RUNNER = """
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import target
except BaseException:
    traceback.print_exc()
    sys.exit(5)

with open("test_code.py") as test_file:
    test = compile(test_file.read(), "<test>", "exec")

# The test sees only the names defined in the reviewed file, never the runner's own.
namespace = {name: value for name, value in vars(target).items() if not name.startswith("__")}

try:
    exec(test, namespace)
except Exception as error:
    traceback.print_exc()
    in_test = traceback.extract_tb(error.__traceback__)[-1].filename == "<test>"
    if isinstance(error, AssertionError):
        sys.exit(3 if in_test else 4)
    sys.exit(6 if in_test else 7)
"""


@dataclass
class ExecutionResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


def _run(script: Path, cwd: str) -> ExecutionResult:
    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(script)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(exit_code=None, stdout="", stderr="", timed_out=True)
    return ExecutionResult(completed.returncode, completed.stdout, completed.stderr)


def execute_python(program: str) -> ExecutionResult:
    """Run a Python program in a separate process with a timeout."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        script = Path(tmp_dir) / "check.py"
        script.write_text(program)
        return _run(script, tmp_dir)


def run_test(source: str, test_code: str) -> ExecutionResult:
    """Run test code against source, reporting where any failure came from."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "target.py").write_text(source)
        (tmp / "test_code.py").write_text(test_code)
        (tmp / "runner.py").write_text(RUNNER)
        return _run(tmp / "runner.py", tmp_dir)


@tool
def run_python(file_path: str, test_code: str) -> str:
    """Run test code against a source file to explore its behavior.

    The file's contents run first, then test_code, in a separate Python
    process with a 5-second timeout. Use print() in test_code to show results.
    Returns the exit code, stdout and stderr.
    """
    source_path = resolve_repo_path(file_path)
    if source_path is None:
        return f"Error: file not found or outside the repository: {file_path}"

    result = execute_python(source_path.read_text() + "\n\n" + test_code)
    if result.timed_out:
        return f"Error: execution exceeded {TIMEOUT_SECONDS} seconds"

    output = (
        f"exit code: {result.exit_code}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return output[:MAX_OUTPUT_CHARS] 