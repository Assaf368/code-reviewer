import sys

from code_reviewer.agents.reviewer import build_reviwer
from code_reviewer.formatting import print_review
from code_reviewer.tools.files import resolve_repo_path
from code_reviewer.verification import verify_issue


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m code_reviewer <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    source_path = resolve_repo_path(file_path)
    if source_path is None:   
        print(f"Error: file not found or outside the repository: {file_path}")
        sys.exit(1)

    agent = build_reviwer()
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Review the file {file_path}"}]
    })

    review = result["structured_response"]
    source = source_path.read_text()
    verifications = [verify_issue(source, issue) for issue in review.issues]

    print_review(review, verifications)


if __name__ == "__main__":
    main()