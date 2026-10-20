import sys

from code_reviewer.formatting import print_review
from code_reviewer.pipeline import review_file
from code_reviewer.tools.files import resolve_repo_path


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m code_reviewer <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    if resolve_repo_path(file_path) is None:
        print(f"Error: file not found or outside the repository: {file_path}")
        sys.exit(1)

    review, verifications = review_file(file_path)
    print_review(review, verifications)


if __name__ == "__main__":
    main()
