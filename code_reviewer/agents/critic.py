from langchain.agents import create_agent

from code_reviewer.prompts import CRITIC_SYSTEM_PROMPT
from code_reviewer.schemas import CriticResult


def build_critic(model):
    """The critic has no tools: it judges reports it is given and returns decisions."""
    return create_agent(
        model=model,
        tools=[],
        system_prompt=CRITIC_SYSTEM_PROMPT,
        response_format=CriticResult,
    )
