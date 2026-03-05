import os
from dotenv import load_dotenv

load_dotenv()


def _get_float_env(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int_env(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "zvaluate_db")
ARGUS_DB_NAME = os.getenv("ARGUS_DB_NAME", "argus-qa")
ARGUS_DATASETS_COLLECTION = os.getenv("ARGUS_DATASETS_COLLECTION", "datasets")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = _get_float_env("OPENAI_TEMPERATURE", 0.2)
OPENAI_MAX_HISTORY_TURNS = _get_int_env("OPENAI_MAX_HISTORY_TURNS", 12)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/ai-runtime.log")
LOG_MAX_BYTES = _get_int_env("LOG_MAX_BYTES", 5 * 1024 * 1024)
LOG_BACKUP_COUNT = _get_int_env("LOG_BACKUP_COUNT", 5)
