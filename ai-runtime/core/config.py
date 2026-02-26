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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = _get_float_env("OPENAI_TEMPERATURE", 0.2)
OPENAI_MAX_HISTORY_TURNS = _get_int_env("OPENAI_MAX_HISTORY_TURNS", 12)
