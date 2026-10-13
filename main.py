from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
import os


load_dotenv()


model = init_chat_model(
    "anthropic:claude-haiku-4-5-20251001",
    default_headers={"anthropic-workspace-id": os.environ["ANTHROPIC_WORKSPACE_ID"]},
)
response = model.invoke('in one sentence, what is a code review?')

print(response.content)