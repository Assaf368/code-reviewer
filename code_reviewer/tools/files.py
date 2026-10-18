from pathlib import Path
from langchain.tools import tool

PROJECT_ROOT = Path.cwd().resolve()


def resolve_repo_path(path: str) -> Path | None:
    """Return the absolute path if it is a file inside the repository, else None."""
    file_path = (PROJECT_ROOT / path).resolve()
    if not file_path.is_relative_to(PROJECT_ROOT) or not file_path.is_file():
        return None
    return file_path

@tool
def read_file(path: str) -> str:
    """Read a source code file from the repository.

    Returns the contents with line numbers in the format 'N | code'.
    Use these numbers when referring to lines in the review.
    """
    file_path = resolve_repo_path(path)

    if file_path is None:
        return f"Error: file not found or outside the repository: {path}"

    lines = file_path.read_text().splitlines()
    numbered = [f"{i:>4} | {line}" for i, line in enumerate(lines, start=1)]
    return "\n".join(numbered)