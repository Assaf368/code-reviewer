"""Run the reviewer on the eval dataset and score it against labels.json.

Usage:
    python -m evals.run_eval                    # run the reviewer, save and score
    python -m evals.run_eval --rescore <json>   # score saved runs against current labels
"""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from code_reviewer.config import MODELNAME
from code_reviewer.pipeline import review_file
from code_reviewer.prompts import REVIEWER_SYSTEM_PROMPT
from code_reviewer.schemas import ReviewResult
from code_reviewer.tools import files
from evals.matching import LEVELS, FileScore, Label, Reported, Run, score_file, total

RUNS = 3

EVALS_DIR = Path(__file__).parent
DATASET_DIR = EVALS_DIR / "dataset"
LABELS_PATH = EVALS_DIR / "labels.json"
RESULTS_DIR = EVALS_DIR / "results"


def load_labels(raw: dict) -> dict[str, list[Label]]:
    return {
        file: [
            Label(f"{file}#{i}", item["category"], tuple(item["lines"]), item["description"])
            for i, item in enumerate(items)
        ]
        for file, items in raw.items()
    }


@contextmanager
def isolated_repo(source: Path) -> Iterator[str]:
    """Copy one file into an empty temp dir and make it the repository root.

    The reviewer's tools then cannot reach labels.json or other dataset files.
    """
    original_root = files.PROJECT_ROOT
    with tempfile.TemporaryDirectory() as tmp_dir:
        shutil.copy(source, tmp_dir)
        files.PROJECT_ROOT = Path(tmp_dir).resolve()
        try:
            yield source.name
        finally:
            files.PROJECT_ROOT = original_root


def run_once(source: Path) -> dict:
    """Review one file in isolation. A failure is recorded, never raised."""
    record = {"file": source.name, "error": None, "issues": None}
    try:
        with isolated_repo(source) as file_name:
            review, verifications = review_file(file_name)
    except Exception as error:
        record["error"] = f"{type(error).__name__}: {error}"
        return record

    record["issues"] = [
        issue.model_dump() | {"verification": verification}
        for issue, verification in zip(review.issues, verifications)
    ]
    return record


def to_run(record: dict) -> Run:
    if record["issues"] is None:
        return Run(record["file"], None, record["error"])
    issues = [
        Reported(i["line"], i["category"], i["verification"], i["title"])
        for i in record["issues"]
    ]
    return Run(record["file"], issues)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def git_state() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=EVALS_DIR
        ).stdout.strip()

    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def format_ratio(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator}" if denominator else "—"


def print_table(scores: list[FileScore]) -> None:
    short = {"all": "all", "confirmed": "conf", "confirmed+crashed": "c+cr"}
    cells = "".join(f"{short[level]:>7}" for level in LEVELS)
    print(f"{'':<24}{'recall':^21}  {'precision':^21}")
    print(f"{'file':<24}{cells}  {cells}{'dup':>6}{'miscat':>8}{'fail':>6}")
    for score in scores:
        recall = "".join(
            f"{format_ratio(c.found, c.expected):>7}" for c in score.levels.values()
        )
        precision = "".join(
            f"{format_ratio(c.correct, c.correct + c.false_positives):>7}"
            for c in score.levels.values()
        )
        print(f"{score.file:<24}{recall}  {precision}"
              f"{score.duplicates:>6}{len(score.miscategorized):>8}{score.failed:>6}")


def print_labels(labels: dict[str, list[Label]], scores: list[FileScore]) -> None:
    by_file = {score.file: score for score in scores}
    for file, file_labels in labels.items():
        score = by_file[file]
        for label in file_labels:
            hits = score.label_hits.get(label.id, [])
            found = sum(1 for statuses in hits if statuses)
            statuses = ", ".join("+".join(s) if s else "—" for s in hits)
            lines = ",".join(map(str, label.lines))
            if not score.runs:
                print(f"{file}:{lines} [{label.category}] → no successful runs")
                continue
            print(f"{file}:{lines} [{label.category}] → found in {found}/{score.runs} runs "
                  f"({statuses})")


def print_details(scores: list[FileScore], failures: list[dict]) -> None:
    for score in scores:
        for issue in score.miscategorized:
            print(f"miscategorized: {score.file}:{issue.line} [{issue.category}] {issue.title}")
    for score in scores:
        if score.unmatched_performance:
            print(f"unmatched performance issues: {score.file}: {score.unmatched_performance}")
    for record in failures:
        print(f"failed run: {record['file']}: {record['error']}")


def report(model: str, records: list[dict], labels: dict[str, list[Label]]) -> None:
    scores = [
        score_file(file, [to_run(r) for r in records if r["file"] == file], file_labels)
        for file, file_labels in labels.items()
    ]

    print(f"\nModel: {model}   Runs per file: {RUNS}")
    print("Note: docstrings in the dataset hint at some bugs, so recall is optimistic.\n")
    print_table(scores + [total(scores)])
    print()
    print_labels(labels, scores)
    print()
    print_details(scores, [r for r in records if r["issues"] is None])


def rescore(path: Path) -> None:
    """Score saved runs against the current labels, without calling the model."""
    saved = json.loads(path.read_text())
    for file, digest in saved["dataset_sha256"].items():
        if sha256((DATASET_DIR / file).read_text()) != digest:
            print(f"Warning: {file} changed since this run; label lines may not match.")
    report(saved["model"], saved["runs"], load_labels(json.loads(LABELS_PATH.read_text())))


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--rescore":
        rescore(Path(sys.argv[2]))
        return

    raw_labels = json.loads(LABELS_PATH.read_text())
    labels = load_labels(raw_labels)
    sources = [DATASET_DIR / file for file in labels]

    records = []
    for source in sources:
        for run in range(1, RUNS + 1):
            print(f"reviewing {source.name} (run {run}/{RUNS})", flush=True)
            records.append(run_once(source) | {"run": run})

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result = {
        "timestamp": timestamp,
        "model": MODELNAME,
        "runs_per_file": RUNS,
        "git": git_state(),
        "prompt_sha256": sha256(REVIEWER_SYSTEM_PROMPT),
        "schema_sha256": sha256(json.dumps(ReviewResult.model_json_schema(), sort_keys=True)),
        "dataset_sha256": {source.name: sha256(source.read_text()) for source in sources},
        "labels": raw_labels,
        "runs": records,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{timestamp}.json"
    path.write_text(json.dumps(result, indent=2) + "\n")

    report(MODELNAME, records, labels)
    print(f"\nRaw results: {path}")


if __name__ == "__main__":
    main()
