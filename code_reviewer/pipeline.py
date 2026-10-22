import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from code_reviewer.agents.critic import build_critic
from code_reviewer.agents.reviewer import build_reviewer
from code_reviewer.config import CRITIC_MODEL, MODELNAME
from code_reviewer.critique import apply_decisions, needs_critic, new_item, render_for_critic
from code_reviewer.schemas import ReviewResult
from code_reviewer.tools.files import resolve_repo_path
from code_reviewer.verification import Verification, verify_issue


@dataclass
class ReviewRun:
    review: ReviewResult
    verifications: list[Verification]
    tool_calls: dict[str, int] = field(default_factory=dict)  # tool name -> number of calls
    tokens: dict[str, int] = field(default_factory=dict)  # reviewer input / output tokens
    questions: list[dict] = field(default_factory=list)  # [{"questions": [...], "answers": "..."}]
    critic: list[dict] = field(default_factory=list)  # one entry per report the critic decided on
    critic_rounds: int = 0
    critic_tokens: dict[str, int] = field(default_factory=dict)


# Gets the reviewer's questions, returns the answers as one text.
AnswerQuestions = Callable[[list[str]], str]


class ReviewState(TypedDict):
    file_path: str
    source: str
    items: list[dict]  # see critique.new_item
    exchanges: list[dict]
    tool_calls: dict[str, int]
    tokens: dict[str, int]
    critic_rounds: int
    critic_log: list[dict]
    critic_tokens: dict[str, int]


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


def build_review_graph(
    answer_questions: AnswerQuestions | None = None,
    model=MODELNAME,
    critic_model=CRITIC_MODEL,
):
    """review -> verify -> (critic -> verify)*, the critic only for weak bug reports.

    critic_model=None turns the critic off.
    """

    def review(state: ReviewState) -> dict:
        agent = build_reviewer(model, ask_user=answer_questions is not None)
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        result = agent.invoke(
            {"messages": [{"role": "user", "content": f"Review the file {state['file_path']}"}]},
            config,
        )
        exchanges = []
        while "__interrupt__" in result:
            questions = result["__interrupt__"][0].value["questions"]
            answers = answer_questions(questions)
            exchanges.append({"questions": questions, "answers": answers})
            result = agent.invoke(Command(resume=answers), config)

        tool_calls, tokens = usage(result["messages"])
        items = [new_item(issue) for issue in result["structured_response"].issues]
        return {"items": items, "exchanges": exchanges, "tool_calls": tool_calls, "tokens": tokens}

    def verify(state: ReviewState) -> dict:
        # Only new reports have no status yet; the rest were verified before.
        items = [
            item if item["verification"] is not None
            else item | {"verification": verify_issue(state["source"], item["issue"])}
            for item in state["items"]
        ]
        return {"items": items}

    def critic(state: ReviewState) -> dict:
        flagged = [index for index, item in enumerate(state["items"]) if needs_critic(item)]
        prompt = render_for_critic(state["source"], state["exchanges"], state["items"], flagged)
        result = build_critic(critic_model).invoke({"messages": [{"role": "user", "content": prompt}]})
        round_number = state["critic_rounds"] + 1
        items, log = apply_decisions(state["items"], flagged, result["structured_response"], round_number)
        _, tokens = usage(result["messages"])
        return {
            "items": items,
            "critic_rounds": round_number,
            "critic_log": state["critic_log"] + log,
            "critic_tokens": dict(Counter(state["critic_tokens"]) + Counter(tokens)),
        }

    def after_verify(state: ReviewState) -> str:
        if critic_model and any(needs_critic(item) for item in state["items"]):
            return "critic"
        return END

    graph = StateGraph(ReviewState)
    graph.add_node("review", review)
    graph.add_node("verify", verify)
    graph.add_node("critic", critic)
    graph.add_edge(START, "review")
    graph.add_edge("review", "verify")
    graph.add_conditional_edges("verify", after_verify, ["critic", END])
    graph.add_edge("critic", "verify")
    return graph.compile()


def review_file(
    file_path: str,
    answer_questions: AnswerQuestions | None = None,
    model=MODELNAME,
    critic_model=CRITIC_MODEL,
) -> ReviewRun:
    """Review one repository file, verify each issue, and let the critic check weak bug reports.

    With answer_questions the reviewer may pause to ask about intended behavior.
    """
    source_path = resolve_repo_path(file_path)
    if source_path is None:
        raise FileNotFoundError(f"file not found or outside the repository: {file_path}")

    graph = build_review_graph(answer_questions, model, critic_model)
    state = graph.invoke({
        "file_path": file_path,
        "source": source_path.read_text(),
        "items": [],
        "exchanges": [],
        "tool_calls": {},
        "tokens": {},
        "critic_rounds": 0,
        "critic_log": [],
        "critic_tokens": {},
    })

    items = state["items"]
    return ReviewRun(
        review=ReviewResult(issues=[item["issue"] for item in items]),
        verifications=[item["verification"] for item in items],
        tool_calls=state["tool_calls"],
        tokens=state["tokens"],
        questions=state["exchanges"],
        critic=state["critic_log"],
        critic_rounds=state["critic_rounds"],
        critic_tokens=state["critic_tokens"],
    )
