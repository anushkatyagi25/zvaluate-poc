from typing import Any

from openai import OpenAI

from core.config import (
    OPENAI_API_KEY,
    OPENAI_MAX_HISTORY_TURNS,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
)
from prompts import SYSTEM_PROMPT


class LLMConfigurationError(Exception):
    pass


class LLMResponseError(Exception):
    pass


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise LLMConfigurationError("OPENAI_API_KEY is not configured")

    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _build_messages(chat_messages: list[dict[str, Any]], user_message: str) -> list[dict[str, str]]:
    prompt = SYSTEM_PROMPT.strip()
    if not prompt:
        raise LLMConfigurationError("System prompt is empty")

    messages: list[dict[str, str]] = [{"role": "system", "content": prompt}]

    history = chat_messages[-OPENAI_MAX_HISTORY_TURNS:] if OPENAI_MAX_HISTORY_TURNS > 0 else []
    for entry in history:
        previous_user_message = str(entry.get("user_message", "")).strip()
        previous_llm_response = str(entry.get("llm_response", "")).strip()

        if previous_user_message:
            messages.append({"role": "user", "content": previous_user_message})
        if previous_llm_response:
            messages.append({"role": "assistant", "content": previous_llm_response})

    messages.append({"role": "user", "content": user_message})
    return messages


def generate_chat_response(chat_messages: list[dict[str, Any]], user_message: str) -> str:
    client = _get_client()
    messages = _build_messages(chat_messages=chat_messages, user_message=user_message)

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=OPENAI_TEMPERATURE,
    )

    content = completion.choices[0].message.content if completion.choices else None
    if not content:
        raise LLMResponseError("LLM returned an empty response")
    return content.strip()
