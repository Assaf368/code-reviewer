import os
from dotenv import load_dotenv


load_dotenv()


MODELNAME = os.getenv("REVIEWER_MODEL", "claude-haiku-4-5")
# The simulated user that answers the reviewer's questions in the eval.
SIMULATED_USER_MODEL = os.getenv("SIMULATED_USER_MODEL", "anthropic:claude-haiku-4-5")
