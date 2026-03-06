import json
from typing import Any

from openai import OpenAI

from core.config import (
    OPENAI_API_KEY,
    OPENAI_MAX_HISTORY_TURNS,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
)
from core.logging_config import get_logger
from prompts import build_system_prompt


class LLMConfigurationError(Exception):
    pass


class LLMResponseError(Exception):
    pass


_client: OpenAI | None = None
logger = get_logger(__name__)


def _get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        logger.error("OpenAI client initialization failed: missing OPENAI_API_KEY")
        raise LLMConfigurationError("OPENAI_API_KEY is not configured")

    global _client
    if _client is None:
        logger.info("Initializing OpenAI client model=%s", OPENAI_MODEL)
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _build_messages(
    chat_messages: list[dict[str, Any]],
    user_message: str,
    dataset_name: str,
    dataset_schema: dict[str, Any],
) -> list[dict[str, str]]:
    prompt = build_system_prompt(dataset_name=dataset_name, dataset_schema=dataset_schema).strip()
    if not prompt:
        logger.error("System prompt was empty while building messages")
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
    logger.info(
        "Built LLM messages dataset=%s history_turns=%s total_messages=%s user_len=%s",
        dataset_name,
        min(len(chat_messages), OPENAI_MAX_HISTORY_TURNS if OPENAI_MAX_HISTORY_TURNS > 0 else 0),
        len(messages),
        len(user_message),
    )
    return messages


def _normalize_llm_output(raw_content: str) -> str:
    try:
        parsed_content = json.loads(raw_content)
    except json.JSONDecodeError:
        logger.warning("LLM output was not valid JSON, returning raw response")
        return raw_content

    if isinstance(parsed_content, dict):
        error_message = parsed_content.get("error")
        if isinstance(error_message, str) and error_message.strip():
            normalized_error = json.dumps({"error": error_message.strip()}, ensure_ascii=True)
            logger.info("LLM output normalized mode=error_json")
            return normalized_error

        status_value = parsed_content.get("status")
        if status_value in {"success", "out_of_scope"}:
            normalized_workflow = json.dumps(parsed_content, indent=2, ensure_ascii=True)
            logger.info("LLM output normalized mode=workflow_json status=%s", status_value)
            return normalized_workflow

        # Backward compatibility for older prompt formats.
        response_value = parsed_content.get("response")
        if response_value is not None:
            if isinstance(response_value, str):
                logger.info("LLM output normalized mode=legacy_response_text")
                return response_value.strip()
            normalized_response = json.dumps(response_value, indent=2, ensure_ascii=True)
            logger.info("LLM output normalized mode=legacy_response_json")
            return normalized_response

        message_value = parsed_content.get("message")
        if isinstance(message_value, str) and message_value.strip():
            questions_value = parsed_content.get("questions")
            if isinstance(questions_value, list):
                questions = [str(item).strip() for item in questions_value if str(item).strip()]
                if questions:
                    message_with_questions = "\n\n".join(
                        [message_value.strip(), "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1))]
                    )
                    logger.info("LLM output normalized mode=message_with_questions count=%s", len(questions))
                    return message_with_questions

            logger.info("LLM output normalized mode=message_text")
            return message_value.strip()

    normalized_content = json.dumps(parsed_content, indent=2, ensure_ascii=True)
    logger.info("LLM output normalized mode=full_json")
    return normalized_content


def generate_chat_response(
    chat_messages: list[dict[str, Any]],
    user_message: str,
    dataset_name: str,
    dataset_schema: dict[str, Any],
) -> str:
    logger.info("LLM generation started dataset=%s model=%s", dataset_name, OPENAI_MODEL)
    client = _get_client()
    messages = _build_messages(
        chat_messages=chat_messages,
        user_message=user_message,
        dataset_name=dataset_name,
        dataset_schema=dataset_schema,
    )

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=OPENAI_TEMPERATURE,
        response_format={"type": "json_object"},
    )

    content = completion.choices[0].message.content if completion.choices else None
    if not content:
        logger.error("LLM generation failed: empty content")
        raise LLMResponseError("LLM returned an empty response")

    raw_content = content.strip()
    normalized_content = _normalize_llm_output(raw_content)
    logger.info("LLM generation completed output_len=%s", len(normalized_content))
    return normalized_content
