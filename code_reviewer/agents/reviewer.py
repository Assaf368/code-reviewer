from langchain.agents import create_agent
from code_reviewer.prompts import REVIEWER_SYSTEM_PROMPT
from code_reviewer.tools.files import read_file
from code_reviewer.tools.execution import run_python
from code_reviewer.config import MODELNAME
from code_reviewer.schemas import ReviewResult

def build_reviwer():

    return create_agent(
        model=MODELNAME,
        tools=[read_file,run_python],
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        response_format=ReviewResult
    )
