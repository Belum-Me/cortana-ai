import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

MEMORY_DB_PATH = "cortana.db"
CHROMA_DB_PATH = "chroma_db"
