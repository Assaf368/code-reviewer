"""Tests for the critic: who reaches it, what its decisions do, and the loop through the graph.

Fake chat models play the reviewer and the critic, so no real model is called.
"""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from code_reviewer.critique import MAX_CRITIC_PASSES, apply_decisions, needs_critic, new_item
from code_reviewer.pipeline import review_file
from code_reviewer.schemas import CriticDecision, CriticResult, Issue
from code_reviewer.tools import files


class FakeModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def issue(line=2, category="bug", fix="f", test_code="assert add(2, 3) == 5", title="t"):
    return Issue(line=line, category=category, severity="major", title=title,
                 explanation="e", fix=fix, test_code=test_code)


def item(verification="confirmed", **kwargs):
    return new_item(issue(**kwargs)) | {"verification": verification}


# --- Who reaches the critic ---

def test_a_proven_bug_does_not_reach_the_critic():
    assert not needs_critic(item("confirmed"))


def test_a_bug_its_test_did_not_prove_reaches_the_critic():
    assert needs_critic(item("not_reproduced"))
    assert needs_critic(item("line_not_reached"))


def test_a_hedging_bug_reaches_the_critic_even_when_confirmed():
    # Like cache.py: "Store a deep copy in set. Optionally deep-copy in get as well."
    assert needs_critic(item("confirmed", fix="Copy in set. Optionally copy in get as well."))


def test_readability_notes_never_reach_the_critic():
    assert not needs_critic(item("not_tested", category="readability", fix="Optionally rename it."))


def test_a_kept_report_does_not_come_back():
    assert not needs_critic(item("line_not_reached") | {"settled": True})


def test_a_report_the_critic_wrote_comes_back_only_if_still_unproven():
    written = new_item(issue(fix="Optionally X."), origin="critic", critic_passes=1)
    assert not needs_critic(written | {"verification": "confirmed"})
    assert needs_critic(written | {"verification": "not_reproduced"})
    assert not needs_critic(written | {"verification": "not_reproduced", "critic_passes": MAX_CRITIC_PASSES})


# --- What the decisions do ---

def decide(action, issues=()):
    return CriticResult(decisions=[CriticDecision(report=1, action=action, reason="r", issues=list(issues))])


def test_keep_settles_the_report():
    items, log = apply_decisions([item("line_not_reached")], [0], decide("keep"), 1)
    assert items[0]["settled"] and items[0]["critic_passes"] == 1
    assert log[0]["action"] == "keep"


def test_drop_removes_the_report():
    items, _ = apply_decisions([item("not_reproduced"), item("confirmed")], [0], decide("drop"), 1)
    assert len(items) == 1 and items[0]["verification"] == "confirmed"


def test_split_replaces_one_report_with_new_unverified_ones():
    split = decide("split", [issue(line=19, title="set"), issue(line=30, title="get")])
    items, log = apply_decisions([item("confirmed", fix="Optionally copy in get.")], [0], split, 1)
    assert [i["issue"].line for i in items] == [19, 30]
    assert all(i["verification"] is None and i["origin"] == "critic" for i in items)
    assert log[0]["new"] == ["set", "get"]


# --- The loop through the graph ---

SOURCE = "def add(a, b):\n    return a - b\n"


def use_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(files, "PROJECT_ROOT", tmp_path.resolve())
    (tmp_path / "a.py").write_text(SOURCE)


def reviewer_reporting(*issues):
    report = {"issues": [i.model_dump() for i in issues]}
    return FakeModel(messages=iter([
        AIMessage(content="", tool_calls=[{"name": "ReviewResult", "args": report, "id": "r1"}]),
    ]))


def critic_answering(*results):
    return FakeModel(messages=iter([
        AIMessage(content="", tool_calls=[{"name": "CriticResult", "args": r.model_dump(), "id": f"c{n}"}])
        for n, r in enumerate(results)
    ]))


def test_critic_fixes_a_weak_test_and_the_new_report_is_verified(monkeypatch, tmp_path):
    use_repo(monkeypatch, tmp_path)
    # The reviewer's test passes on the buggy code (3 - 2 == 1), so it proves nothing.
    reviewer = reviewer_reporting(issue(test_code="assert add(3, 2) == 1"))
    critic = critic_answering(decide("revise", [issue(test_code="assert add(2, 3) == 5")]))

    run = review_file("a.py", model=reviewer, critic_model=critic)

    assert run.verifications == ["confirmed"]
    assert run.critic_rounds == 1
    assert run.critic[0]["action"] == "revise"


def test_no_critic_call_when_every_bug_is_proven(monkeypatch, tmp_path):
    use_repo(monkeypatch, tmp_path)
    reviewer = reviewer_reporting(issue(test_code="assert add(2, 3) == 5"))
    critic = critic_answering()  # would fail if it were called

    run = review_file("a.py", model=reviewer, critic_model=critic)

    assert run.verifications == ["confirmed"]
    assert run.critic_rounds == 0


def test_critic_runs_at_most_twice(monkeypatch, tmp_path):
    use_repo(monkeypatch, tmp_path)
    weak = issue(test_code="assert add(3, 2) == 1")
    reviewer = reviewer_reporting(weak)
    critic = critic_answering(decide("revise", [weak]), decide("revise", [weak]), decide("revise", [weak]))

    run = review_file("a.py", model=reviewer, critic_model=critic)

    assert run.critic_rounds == 2
    assert run.verifications == ["not_reproduced"]


def test_without_a_critic_model_the_critic_is_off(monkeypatch, tmp_path):
    use_repo(monkeypatch, tmp_path)
    reviewer = reviewer_reporting(issue(test_code="assert add(3, 2) == 1"))

    run = review_file("a.py", model=reviewer, critic_model=None)

    assert run.verifications == ["not_reproduced"]
    assert run.critic_rounds == 0
