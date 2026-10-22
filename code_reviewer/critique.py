"""Which reports go to the critic, and how its decisions change the review. No model here."""

import re

from code_reviewer.schemas import CriticResult

# A report reaches the critic at most this many times.
MAX_CRITIC_PASSES = 2

# Statuses where the report's own test did not prove the bug.
WEAK_STATUSES = {"not_reproduced", "line_not_reached", "test_error", "inconclusive", "unverified", "missing_test"}

# Words that show the reviewer was unsure, as in "optionally deep-copy in get too".
HEDGE = re.compile(r"\b(optional|optionally|consider|might want|if callers? may|could also)\b", re.IGNORECASE)

STATUS_MEANING = {
    "confirmed": "the test failed on an assert in the test: the bug is shown",
    "crashed": "the reviewed code raised an exception during the test",
    "not_reproduced": "the test passed, so the claimed bug did not show",
    "line_not_reached": "the test failed, but the reported line never ran, so the failure proves something else",
    "inconclusive": "an assert inside the reviewed code failed",
    "test_error": "the test itself is broken (syntax error, unknown name, or timeout)",
    "source_error": "the file failed to load",
    "unverified": "no test; the reviewer said it cannot be tested with a simple assert",
    "missing_test": "no test was written",
}


def new_item(issue, origin: str = "reviewer", critic_passes: int = 0) -> dict:
    """One report in the review, with what is known about it."""
    return {"issue": issue, "verification": None, "settled": False, "origin": origin, "critic_passes": critic_passes}


def hedges(issue) -> bool:
    return bool(HEDGE.search(f"{issue.explanation} {issue.fix}"))


def needs_critic(item: dict) -> bool:
    """Only weak bug reports go to the critic. Readability notes never do."""
    issue = item["issue"]
    if item["settled"] or issue.category != "bug" or item["critic_passes"] >= MAX_CRITIC_PASSES:
        return False
    weak = item["verification"] in WEAK_STATUSES
    if item["origin"] == "reviewer":
        return weak or hedges(issue)
    # A report the critic wrote comes back only if its test still did not prove it.
    return weak


def render_for_critic(source: str, exchanges: list[dict], items: list[dict], flagged: list[int]) -> str:
    """The critic's input: the numbered file, the user's answers, and the flagged reports."""
    numbered = "\n".join(f"{n:>4} | {line}" for n, line in enumerate(source.splitlines(), start=1))
    parts = [f"File:\n{numbered}"]
    if exchanges:
        answers = "\n".join(
            "\n".join(f"Q: {q}" for q in exchange["questions"]) + f"\nA: {exchange['answers']}"
            for exchange in exchanges
        )
        parts.append(f"The user's answers about intended behavior:\n{answers}")
    reports = []
    for number, index in enumerate(flagged, start=1):
        item = items[index]
        issue = item["issue"].model_dump(exclude={"category", "severity", "example"})
        status = item["verification"]
        reports.append(f"Report {number}: {issue}\nVerification: {status} ({STATUS_MEANING.get(status, '')})")
    parts.append("Reports to check:\n" + "\n\n".join(reports))
    return "\n\n".join(parts)


def apply_decisions(items: list[dict], flagged: list[int], result: CriticResult, round_number: int):
    """Apply the critic's decisions. Returns the new items and a log of what changed."""
    by_report = {decision.report: decision for decision in result.decisions}
    decision_for = {index: by_report.get(number) for number, index in enumerate(flagged, start=1)}

    new_items, log = [], []
    for index, item in enumerate(items):
        if index not in decision_for:
            new_items.append(item)
            continue
        decision = decision_for[index]
        passes = item["critic_passes"] + 1
        action = decision.action if decision else "keep"
        log.append({
            "round": round_number,
            "line": item["issue"].line,
            "title": item["issue"].title,
            "action": action,
            "reason": decision.reason if decision else "no decision returned",
            "new": [issue.title for issue in decision.issues] if decision else [],
        })
        if action == "drop":
            continue
        if action in ("revise", "split") and decision.issues:
            new_items += [new_item(issue, "critic", passes) for issue in decision.issues]
            continue
        # keep, or revise/split without a new report: the report stays and is settled.
        new_items.append(item | {"settled": True, "critic_passes": passes})
    return new_items, log
