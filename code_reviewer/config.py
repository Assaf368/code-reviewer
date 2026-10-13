import os
from dotenv import load_dotenv


load_dotenv()


MODELNAME = os.getenv("REVIEWER_MODEL", "claude-haiku-4-5")