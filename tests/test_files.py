"""Tests for read_file and the repository boundary."""

from code_reviewer.tools import files


def use_repo(monkeypatch, tmp_path):
    """Point the tools at a temporary folder that acts as the repository."""
    monkeypatch.setattr(files, "PROJECT_ROOT", tmp_path.resolve())


def test_read_file_adds_line_numbers(monkeypatch, tmp_path):
    use_repo(monkeypatch, tmp_path)
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n")

    output = files.read_file.invoke({"path": "a.py"})

    assert output == "   1 | x = 1\n   2 | y = 2"


def test_missing_file_returns_error_message(monkeypatch, tmp_path):
    use_repo(monkeypatch, tmp_path)

    output = files.read_file.invoke({"path": "nope.py"})

    assert output.startswith("Error:")


def test_path_outside_repository_is_refused(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "secret.txt").write_text("password")
    use_repo(monkeypatch, repo)

    output = files.read_file.invoke({"path": "../secret.txt"})

    assert output.startswith("Error:")
    assert "password" not in output


def test_directory_is_not_a_file(monkeypatch, tmp_path):
    use_repo(monkeypatch, tmp_path)
    (tmp_path / "folder").mkdir()

    assert files.resolve_repo_path("folder") is None