"""Match reported issues to labels and compute the metrics. Pure: no model, no I/O."""

from dataclasses import dataclass, field

# Which verification statuses count at each level. None means every bug report.
LEVELS = {
    "all": None,
    "confirmed": {"confirmed"},
    "confirmed+crashed": {"confirmed", "crashed"},
}
LABELED_CATEGORIES = ("bug", "performance")


@dataclass(frozen=True)
class Label:
    id: str  # "<file>#<index in labels.json>"
    category: str
    lines: tuple[int, ...]
    description: str = ""


@dataclass(frozen=True)
class Reported:
    """What matching needs from one reported Issue, after verification."""
    line: int
    category: str
    verification: str
    title: str = ""


@dataclass
class Run:
    file: str
    issues: list[Reported] | None  # None means the run failed
    error: str | None = None


def ratio(numerator: int, denominator: int) -> float | None:
    """None when there is nothing to measure, so it is never confused with 0."""
    return numerator / denominator if denominator else None


@dataclass
class LevelCounts:
    found: int = 0  # bug labels found, summed over runs
    expected: int = 0  # bug labels x successful runs
    correct: int = 0  # bug issues that match a bug label
    false_positives: int = 0  # bug issues that match nothing

    @property
    def recall(self) -> float | None:
        return ratio(self.found, self.expected)

    @property
    def precision(self) -> float | None:
        return ratio(self.correct, self.correct + self.false_positives)


@dataclass
class FileScore:
    file: str
    levels: dict[str, LevelCounts] = field(
        default_factory=lambda: {level: LevelCounts() for level in LEVELS}
    )
    runs: int = 0  # successful runs
    failed: int = 0
    duplicates: int = 0
    miscategorized: list[Reported] = field(default_factory=list)
    unmatched_performance: int = 0
    other: int = 0  # security and readability issues, not scored
    # label id -> one entry per successful run: statuses of the issues that matched it
    label_hits: dict[str, list[list[str]]] = field(default_factory=dict)


def is_near(issue: Reported, label: Label) -> bool:
    return any(abs(issue.line - line) <= 1 for line in label.lines)


def matches(issue: Reported, label: Label) -> bool:
    return issue.category == label.category and is_near(issue, label)


def is_miscategorized(issue: Reported, labels: list[Label]) -> bool:
    """Near a label of another category, and matching no label of its own."""
    if any(matches(issue, label) for label in labels):
        return False
    return any(is_near(issue, label) and label.category != issue.category for label in labels)


def counts_at(issue: Reported, level: str) -> bool:
    statuses = LEVELS[level]
    return statuses is None or issue.verification in statuses


def score_file(file: str, runs: list[Run], labels: list[Label]) -> FileScore:
    score = FileScore(file)
    bug_labels = [label for label in labels if label.category == "bug"]

    for run in runs:
        if run.issues is None:
            score.failed += 1
            continue
        score.runs += 1

        for label in labels:
            hits = [issue for issue in run.issues if matches(issue, label)]
            score.label_hits.setdefault(label.id, []).append([i.verification for i in hits])
            score.duplicates += max(0, len(hits) - 1)

        scored_bugs = []
        for issue in run.issues:
            if is_miscategorized(issue, labels):
                score.miscategorized.append(issue)
            elif issue.category == "bug":
                scored_bugs.append(issue)
            elif issue.category == "performance":
                if not any(matches(issue, label) for label in labels):
                    score.unmatched_performance += 1
            else:
                score.other += 1

        for level, counts in score.levels.items():
            at_level = [issue for issue in scored_bugs if counts_at(issue, level)]
            correct = sum(any(matches(i, label) for label in bug_labels) for i in at_level)
            counts.expected += len(bug_labels)
            counts.found += sum(any(matches(i, label) for i in at_level) for label in bug_labels)
            counts.correct += correct
            counts.false_positives += len(at_level) - correct

    return score


def total(scores: list[FileScore]) -> FileScore:
    """Pool the counts of all files, so ratios weigh every label equally."""
    result = FileScore("TOTAL")
    for score in scores:
        for level, counts in score.levels.items():
            pooled = result.levels[level]
            pooled.found += counts.found
            pooled.expected += counts.expected
            pooled.correct += counts.correct
            pooled.false_positives += counts.false_positives
        result.runs += score.runs
        result.failed += score.failed
        result.duplicates += score.duplicates
        result.miscategorized += score.miscategorized
        result.unmatched_performance += score.unmatched_performance
        result.other += score.other
        result.label_hits.update(score.label_hits)
    return result
