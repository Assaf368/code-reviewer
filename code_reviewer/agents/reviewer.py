from langchain.agents import create_agent
import os
from code_reviewer.prompts import REVIEWER_SYSTEM_PROMPT
from code_reviewer.tools.files import read_file
from code_reviewer.config import MODELNAME

def build_reviwer():

    return create_agent(
        model=MODELNAME,
        tools=[read_file],
        system_prompt=REVIEWER_SYSTEM_PROMPT,
    )
