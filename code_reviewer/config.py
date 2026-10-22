import os
from dotenv import load_dotenv


load_dotenv()


MODELNAME = os.getenv("REVIEWER_MODEL", "anthropic:claude-sonnet-5-5")
# The simulated user that answers the reviewer's questions in the eval.
SIMULATED_USER_MODEL = os.getenv("SIMULATED_USER_MODEL", "anthropic:claude-haiku-4-5")

# A stronger model that checks weak bug reports after verification.
CRITIC_MODEL = os.getenv("CRITIC_MODEL", "anthropic:claude-opus-5-5")
