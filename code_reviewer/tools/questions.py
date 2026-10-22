from langchain.tools import tool
from langgraph.types import interrupt

MAX_QUESTION_ROUNDS = 2


def make_ask_user():
    """Build an ask_user tool for one review. It allows MAX_QUESTION_ROUNDS calls."""
    rounds = 0

    @tool
    def ask_user(questions: list[str]) -> str:
        """Ask the user about intended behavior that the docstrings, names and code do not settle.

        Put all current questions in one call. Returns the user's answers.
        """
        nonlocal rounds
        if rounds >= MAX_QUESTION_ROUNDS:
            return "No more questions. Decide with what you know."
        # interrupt() pauses the agent until the caller resumes it with the answers.
        # On resume the tool runs again from the top, so the counter goes up only after it.
        answers = interrupt({"questions": questions})
        rounds += 1
        return answers

    return ask_user
