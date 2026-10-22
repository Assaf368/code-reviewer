"""A simulated developer that answers the reviewer's questions during the eval.

It knows the intended behavior from questions.json, but never the verdict
(bug or correct), so it cannot leak the answer key.
"""

from langchain.chat_models import init_chat_model

from code_reviewer.config import SIMULATED_USER_MODEL

NO_REQUIREMENT = "I have no requirement about that."

SIMULATED_USER_PROMPT = """You are the developer who wrote the code under review. A reviewer asks
you questions about what the code is supposed to do. You know only the
intended behavior below.

Intended behavior:
{points}

Rules:
- Answer only what is asked: one short answer per question, numbered like the questions.
- If a question is not about one of the points above, answer "{no_requirement}"
- Describe intended behavior only. Never say whether the code is right or wrong,
  and never mention bugs, line numbers or tests.
- Do not add anything the question did not ask about.
"""


def build_prompt(points: list[dict]) -> str:
    lines = "\n".join(f"- About \"{point['question']}\": {point['intent']}" for point in points)
    return SIMULATED_USER_PROMPT.format(points=lines, no_requirement=NO_REQUIREMENT)


def make_simulated_user(points: list[dict], model=None):
    """Return an answer_questions function for one dataset file."""

    def answer(questions: list[str]) -> str:
        numbered = "\n".join(f"{n}. {q}" for n, q in enumerate(questions, start=1))
        if not points:
            # Nothing is unclear in this file, so every question gets the same reply.
            return "\n".join(f"{n}. {NO_REQUIREMENT}" for n in range(1, len(questions) + 1))
        chat = model or init_chat_model(SIMULATED_USER_MODEL)
        reply = chat.invoke([
            {"role": "system", "content": build_prompt(points)},
            {"role": "user", "content": numbered},
        ])
        return reply.content

    return answer
