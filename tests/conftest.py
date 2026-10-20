import os

# Unit tests must not send traces to LangSmith. load_dotenv() keeps variables
# that are already set, so this wins over LANGSMITH_TRACING=true in .env.
os.environ["LANGSMITH_TRACING"] = "false"
