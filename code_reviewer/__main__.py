import argparse
import sys

from code_reviewer.config import CRITIC_MODEL
from code_reviewer.formatting import print_critic, print_review
from code_reviewer.pipeline import review_file
from code_reviewer.tools.files import resolve_repo_path


def ask_in_terminal(questions: list[str]) -> str:
    """Show the reviewer's questions and read one answer per question."""
    print("\nThe reviewer has questions about the intended behavior:")
    answers = []
    for number, question in enumerate(questions, start=1):
        print(f"  {number}. {question}")
        answers.append(f"{number}. {input('     > ').strip()}")
    return "\n".join(answers)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m code_reviewer", description="Review a Python file.")
    parser.add_argument("file_path")
    parser.add_argument("--no-questions", action="store_true",
                        help="review without asking about intended behavior")
    parser.add_argument("--no-critic", action="store_true",
                        help="do not send weak bug reports to the critic model")
    args = parser.parse_args()

    if resolve_repo_path(args.file_path) is None:
        print(f"Error: file not found or outside the repository: {args.file_path}")
        sys.exit(1)

    run = review_file(
        args.file_path,
        None if args.no_questions else ask_in_terminal,
        critic_model=None if args.no_critic else CRITIC_MODEL,
    )
    print_critic(run.critic)
    print_review(run.review, run.verifications)


if __name__ == "__main__":
    main()
