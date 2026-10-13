from pathlib import Path
from langchain.tools import tool

PROJECT_ROOT = Path.cwd().resolve()


@tool
def read_file(path:str) -> str:

    """Read a source code file from the repository and return its full contents."""


    file_path = (PROJECT_ROOT / path).resolve()

    if not file_path.is_relative_to(PROJECT_ROOT):
        return 'Error :  access outside the repository is not allowed.'
    if not file_path.is_file():
        return f'Error : file not found : {path}'

    lines = file_path.read_text().splitlines()
    numbered = [f"{i:>4} | {line}" for i, line in enumerate(lines, start=1)]
    return "\n".join(numbered)