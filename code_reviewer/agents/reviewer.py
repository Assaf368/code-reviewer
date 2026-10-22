from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from code_reviewer.config import MODELNAME
from code_reviewer.prompts import QUESTIONS_PROMPT, REVIEWER_SYSTEM_PROMPT
from code_reviewer.schemas import ReviewResult
from code_reviewer.tools.execution import run_python
from code_reviewer.tools.files import read_file
from code_reviewer.tools.questions import make_ask_user


def build_reviwer(model=MODELNAME, ask_user: bool = False):
    """Build the reviewer agent. With ask_user it can pause to ask the user questions."""
    if not ask_user:
        return create_agent(
            model=model,
            tools=[read_file, run_python],
            system_prompt=REVIEWER_SYSTEM_PROMPT,
            response_format=ReviewResult,
        )

    # A checkpointer keeps the agent's state while it waits for the answers.
    return create_agent(
        model=model,
        tools=[read_file, run_python, make_ask_user()],
        system_prompt=REVIEWER_SYSTEM_PROMPT + QUESTIONS_PROMPT,
        response_format=ReviewResult,
        checkpointer=InMemorySaver(),
    )
