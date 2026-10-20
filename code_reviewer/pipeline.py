from code_reviewer.agents.reviewer import build_reviwer
from code_reviewer.schemas import ReviewResult
from code_reviewer.tools.files import resolve_repo_path
from code_reviewer.verification import Verification, verify_issue


def review_file(file_path: str) -> tuple[ReviewResult, list[Verification]]:
    """Run the reviewer on one repository file, then verify each reported issue."""
    source_path = resolve_repo_path(file_path)
    if source_path is None:
        raise FileNotFoundError(f"file not found or outside the repository: {file_path}")

    agent = build_reviwer()
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Review the file {file_path}"}]
    })

    review = result["structured_response"]
    source = source_path.read_text()
    verifications = [verify_issue(source, issue) for issue in review.issues]
    return review, verifications
