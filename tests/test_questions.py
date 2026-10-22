"""Tests for asking the user: the pause-and-resume loop, the limit, and the simulated user.

A fake chat model plays the reviewer, so no real model is called.
"""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from code_reviewer.pipeline import review_file
from code_reviewer.tools import files
from code_reviewer.tools.questions import MAX_QUESTION_ROUNDS
from evals.simulated_user import NO_REQUIREMENT, build_prompt, make_simulated_user


class FakeReviewer(GenericFakeChatModel):
    """Returns the given messages in order. Tools are accepted and ignored."""

    def bind_tools(self, tools, **kwargs):
        return self


def call(name, args, number):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{number}"}])


def finish(number):
    return call("ReviewResult", {"issues": []}, number)


def use_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(files, "PROJECT_ROOT", tmp_path.resolve())
    (tmp_path / "a.py").write_text("x = 1\n")


def test_questions_are_answered_and_the_review_continues(monkeypatch, tmp_path):
    use_repo(monkeypatch, tmp_path)
    reviewer = FakeReviewer(messages=iter([call("ask_user", {"questions": ["Q1", "Q2"]}, 1), finish(2)]))
    asked = []

    def answer(questions):
        asked.append(questions)
        return "1. yes\n2. no"

    run = review_file("a.py", answer, model=reviewer)

    assert asked == [["Q1", "Q2"]]
    assert run.questions == [{"questions": ["Q1", "Q2"], "answers": "1. yes\n2. no"}]
    assert run.tool_calls["ask_user"] == 1


def test_only_two_rounds_of_questions_reach_the_user(monkeypatch, tmp_path):
    use_repo(monkeypatch, tmp_path)
    reviewer = FakeReviewer(messages=iter([
        call("ask_user", {"questions": ["Q1"]}, 1),
        call("ask_user", {"questions": ["Q2"]}, 2),
        call("ask_user", {"questions": ["Q3"]}, 3),
        finish(4),
    ]))
    asked = []

    run = review_file("a.py", lambda questions: asked.append(questions) or "ok", model=reviewer)

    assert len(asked) == MAX_QUESTION_ROUNDS == 2
    assert [exchange["questions"] for exchange in run.questions] == [["Q1"], ["Q2"]]


def test_without_an_answer_function_there_is_no_ask_user_tool(monkeypatch, tmp_path):
    use_repo(monkeypatch, tmp_path)
    reviewer = FakeReviewer(messages=iter([finish(1)]))

    run = review_file("a.py", model=reviewer)

    assert run.questions == []
    assert "ask_user" not in run.tool_calls


# --- Simulated user ---

def test_simulated_user_with_nothing_unclear_has_no_requirement():
    answer = make_simulated_user([])
    assert answer(["Is X intended?", "And Y?"]) == f"1. {NO_REQUIREMENT}\n2. {NO_REQUIREMENT}"


def test_simulated_user_prompt_never_contains_the_verdict():
    points = [{"question": "Which rate do VIP users pay?", "intent": "VIP pays 10%.", "verdict": "SECRET"}]
    prompt = build_prompt(points)
    assert "VIP pays 10%." in prompt
    assert "SECRET" not in prompt


def test_simulated_user_returns_the_model_reply():
    model = FakeReviewer(messages=iter([AIMessage(content="1. VIP pays 10%.")]))
    answer = make_simulated_user([{"question": "q", "intent": "VIP pays 10%.", "verdict": "bug"}], model)
    assert answer(["Which rate do VIP users pay?"]) == "1. VIP pays 10%."
