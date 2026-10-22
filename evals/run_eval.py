"""Run the reviewer on the eval dataset and score it against labels.json.

Usage:
    python -m evals.run_eval                    # run the reviewer, save and score
    python -m evals.run_eval --only a.py b.py   # run only these dataset files
    python -m evals.run_eval --no-questions     # the reviewer cannot ask the simulated user
    python -m evals.run_eval --rescore <json>   # score saved runs against current labels
    python -m evals.run_eval --reverify <json>  # also rerun the saved tests with current verification
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from langsmith import traceable

from code_reviewer.config import MODELNAME
from code_reviewer.pipeline import review_file
from code_reviewer.prompts import REVIEWER_SYSTEM_PROMPT
from code_reviewer.schemas import Issue, ReviewResult
from code_reviewer.tools import files
from code_reviewer.verification import verify_issue
from evals.matching import LEVELS, FileScore, Label, Reported, Run, score_file, total
from evals.simulated_user import make_simulated_user

RUNS = 3

EVALS_DIR = Path(__file__).parent
DATASET_DIR = EVALS_DIR / "dataset"
LABELS_PATH = EVALS_DIR / "labels.json"
QUESTIONS_PATH = EVALS_DIR / "questions.json"
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


@traceable(name="review case", process_inputs=lambda inputs: {"file": inputs["source"].name})
def run_once(source: Path, points: list[dict] | None = None) -> dict:
    """Review one file in isolation. A failure is recorded, never raised.

    points are the unclear spots the simulated user knows about. None means the
    reviewer cannot ask questions; [] means it can, but nothing is unclear.
    """
    record = {"file": source.name, "error": None, "issues": None}
    answer_questions = make_simulated_user(points) if points is not None else None
    start = time.perf_counter()
    try:
        with isolated_repo(source) as file_name:
            outcome = review_file(file_name, answer_questions)
    except Exception as error:
        record["error"] = f"{type(error).__name__}: {error}"
        return record
    finally:
        record["seconds"] = round(time.perf_counter() - start, 1)

    record["tool_calls"] = outcome.tool_calls
    record["questions"] = outcome.questions
    record["tokens"] = outcome.tokens
    record["issues"] = [
        issue.model_dump() | {"verification": verification}
        for issue, verification in zip(outcome.review.issues, outcome.verifications)
    ]
    return record


def describe(record: dict) -> str:
    """One progress line: time, tool calls and tokens, or the error."""
    if record["error"]:
        return f"failed after {record['seconds']}s: {record['error'][:120]}"
    tools = ", ".join(f"{name}×{count}" for name, count in record["tool_calls"].items())
    tokens = record["tokens"]
    asked = sum(len(exchange["questions"]) for exchange in record.get("questions", []))
    return (f"{record['seconds']}s, {len(record['issues'])} issues, {asked} questions, "
            f"tools: {tools or 'none'}, tokens: {tokens.get('input', 0)} in / {tokens.get('output', 0)} out")


def to_run(record: dict) -> Run:
    if record["issues"] is None:
        return Run(record["file"], None, record["error"])
    issues = [
        Reported(i["line"], i["category"], i["verification"], i["title"])
        for i in record["issues"]
    ]
    asked = sum(len(exchange["questions"]) for exchange in record.get("questions", []))
    return Run(record["file"], issues, questions=asked)


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
    print(f"{'file':<24}{cells}  {cells}{'dup':>6}{'miscat':>8}{'fail':>6}{'q':>5}")
    for score in scores:
        recall = "".join(
            f"{format_ratio(c.found, c.expected):>7}" for c in score.levels.values()
        )
        precision = "".join(
            f"{format_ratio(c.correct, c.correct + c.false_positives):>7}"
            for c in score.levels.values()
        )
        print(f"{score.file:<24}{recall}  {precision}"
              f"{score.duplicates:>6}{len(score.miscategorized):>8}{score.failed:>6}{score.questions:>5}")


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


def print_questions(records: list[dict], unclear_files: set[str]) -> None:
    """Every question and answer, so a leaking simulated user is easy to spot."""
    unneeded = 0
    for record in records:
        for exchange in record.get("questions") or []:
            if record["file"] not in unclear_files:
                unneeded += len(exchange["questions"])
            print(f"questions: {record['file']} run {record['run']}")
            for question in exchange["questions"]:
                print(f"  Q: {question}")
            for line in str(exchange["answers"]).splitlines():
                print(f"  A: {line}")
    print(f"questions on files with a clear contract: {unneeded}")


def print_details(scores: list[FileScore], failures: list[dict]) -> None:
    for score in scores:
        for issue in score.false_positive_issues:
            print(f"false positive: {score.file}:{issue.line} [{issue.verification}] {issue.title}")
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
    if any(r.get("questions") for r in records):
        print()
        print_questions(records, set(json.loads(QUESTIONS_PATH.read_text())))


def reverify(records: list[dict]) -> list[dict]:
    """Rerun each saved test with the current verify_issue. No model calls."""
    updated = []
    for record in records:
        if record["issues"] is None:
            updated.append(record)
            continue
        source = (DATASET_DIR / record["file"]).read_text()
        issues = []
        for saved in record["issues"]:
            issue = Issue(**{k: v for k, v in saved.items() if k != "verification"})
            verification = verify_issue(source, issue)
            if verification != saved["verification"]:
                print(f"{record['file']} run {record['run']} line {saved['line']}: "
                      f"{saved['verification']} → {verification}")
            issues.append(saved | {"verification": verification})
        updated.append(record | {"issues": issues})
    return updated


def rescore(path: Path, verify_again: bool = False) -> None:
    """Score saved runs against the current labels, without calling the model."""
    saved = json.loads(path.read_text())
    for file, digest in saved["dataset_sha256"].items():
        if sha256((DATASET_DIR / file).read_text()) != digest:
            print(f"Warning: {file} changed since this run; label lines may not match.")
    records = reverify(saved["runs"]) if verify_again else saved["runs"]
    report(saved["model"], records, load_labels(json.loads(LABELS_PATH.read_text())))


def save(path: Path, result: dict) -> None:
    path.write_text(json.dumps(result, indent=2) + "\n")


@traceable(
    name="run_eval",
    process_inputs=lambda inputs: {
        "files": [source.name for source in inputs["sources"]],
        "results_file": inputs["path"].name,
    },
)
def run_all(sources: list[Path], result: dict, path: Path, questions: dict | None = None) -> None:
    """Review every source RUNS times. Saves after each run, so a stopped eval keeps its work."""
    for source in sources:
        for run in range(1, RUNS + 1):
            print(f"reviewing {source.name} (run {run}/{RUNS}) ... ", end="", flush=True)
            points = None if questions is None else questions.get(source.name, [])
            record = run_once(source, points, langsmith_extra={
                "name": f"{source.name} run {run}",
                "metadata": {"file": source.name, "run": run, "model": MODELNAME},
            }) | {"run": run}
            print(describe(record), flush=True)
            result["runs"].append(record)
            save(path, result)
    result["complete"] = True
    save(path, result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and score the reviewer eval.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--rescore", type=Path, help="score a saved run against current labels")
    mode.add_argument("--reverify", type=Path, help="like --rescore, but rerun the saved tests first")
    mode.add_argument("--only", nargs="+", metavar="FILE", help="run only these dataset files")
    parser.add_argument("--no-questions", action="store_true",
                        help="the reviewer cannot ask the simulated user questions")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rescore or args.reverify:
        rescore(args.rescore or args.reverify, verify_again=args.reverify is not None)
        return

    raw_labels = json.loads(LABELS_PATH.read_text())
    if args.only:
        unknown = set(args.only) - set(raw_labels)
        if unknown:
            raise SystemExit(f"Not in labels.json: {', '.join(sorted(unknown))}")
        raw_labels = {file: items for file, items in raw_labels.items() if file in args.only}
    labels = load_labels(raw_labels)
    sources = [DATASET_DIR / file for file in labels]

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
        "questions_enabled": not args.no_questions,
        "complete": False,
        "runs": [],
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{timestamp}.json"

    questions = None if args.no_questions else json.loads(QUESTIONS_PATH.read_text())
    run_all(sources, result, path, questions, langsmith_extra={
        "metadata": {"model": MODELNAME, "runs_per_file": RUNS, "results_file": path.name},
        "tags": ["eval", MODELNAME],
    })
    records = result["runs"]

    report(MODELNAME, records, labels)
    print(f"\nRaw results: {path}")


if __name__ == "__main__":
    main()
