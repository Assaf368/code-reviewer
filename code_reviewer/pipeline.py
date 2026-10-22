import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from langgraph.types import Command

from code_reviewer.agents.reviewer import build_reviwer
from code_reviewer.config import MODELNAME
from code_reviewer.schemas import ReviewResult
from code_reviewer.tools.files import resolve_repo_path
from code_reviewer.verification import Verification, verify_issue


@dataclass
class ReviewRun:
    review: ReviewResult
    verifications: list[Verification]
    tool_calls: dict[str, int] = field(default_factory=dict)  # tool name -> number of calls
    tokens: dict[str, int] = field(default_factory=dict)  # input / output tokens over all model calls
    questions: list[dict] = field(default_factory=list)  # [{"questions": [...], "answers": "..."}]


# Gets the reviewer's questions, returns the answers as one text.
AnswerQuestions = Callable[[list[str]], str]


def usage(messages: list) -> tuple[dict[str, int], dict[str, int]]:
    """Count tool calls by name and sum token usage over the agent's messages."""
    tool_calls = Counter()
    tokens = Counter()
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            tool_calls[call["name"]] += 1
        metadata = getattr(message, "usage_metadata", None) or {}
        tokens["input"] += metadata.get("input_tokens", 0)
        tokens["output"] += metadata.get("output_tokens", 0)
    return dict(tool_calls), dict(tokens)


def review_file(
    file_path: str,
    answer_questions: AnswerQuestions | None = None,
    model=MODELNAME,
) -> ReviewRun:
    """Run the reviewer on one repository file, then verify each reported issue.

    With answer_questions the reviewer may pause to ask about intended behavior;
    each pause is answered by answer_questions and the review continues.
    """
    source_path = resolve_repo_path(file_path)
    if source_path is None:
        raise FileNotFoundError(f"file not found or outside the repository: {file_path}")

    agent = build_reviwer(model, ask_user=answer_questions is not None)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Review the file {file_path}"}]},
        config,
    )

    exchanges = []
    while "__interrupt__" in result:
        questions = result["__interrupt__"][0].value["questions"]
        answers = answer_questions(questions)
        exchanges.append({"questions": questions, "answers": answers})
        result = agent.invoke(Command(resume=answers), config)

    review = result["structured_response"]
    source = source_path.read_text()
    verifications = [verify_issue(source, issue) for issue in review.issues]
    tool_calls, tokens = usage(result["messages"])
    return ReviewRun(review, verifications, tool_calls, tokens, exchanges)
