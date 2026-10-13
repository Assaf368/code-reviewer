from code_reviewer.schemas import ReviewResult

SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2}


def print_review(review: ReviewResult) -> None:
    print(f"\n{review.summary}\n")

    for issue in sorted(review.issues, key=lambda i: SEVERITY_ORDER[i.severity]):
        print(f"[{issue.severity.upper()}] line {issue.line} · {issue.category} · {issue.title}")
        print(f"    {issue.explanation}")
        if issue.example:
            print(f"    Example: {issue.example}")
        print(f"    Fix: {issue.fix}\n")