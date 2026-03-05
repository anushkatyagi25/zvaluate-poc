import asyncio
import json
import uuid
from typing import Any

import socketio

from chats.repository import append_chat_message, get_chat
from core.logging_config import get_logger
from services.dataset_schema_service import fetch_dataset_schema
from services.llm_service import LLMConfigurationError, LLMResponseError, generate_chat_response

logger = get_logger(__name__)
STREAM_CHUNK_SIZE = 48


def _resolve_error_message(exc: Exception) -> str:
    if isinstance(exc, (LLMConfigurationError, LLMResponseError)):
        return str(exc)
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, RuntimeError):
        return str(exc)
    return "Failed to process your request"


def _validate_message_payload(data: dict[str, Any]) -> tuple[str, str, str, str]:
    chat_id = (data or {}).get("chat_id", "")
    message_text = (data or {}).get("message", "")
    dataset_name = (data or {}).get("dataset_name", "")
    dataset_url = (data or {}).get("dataset_url", "")

    if not isinstance(chat_id, str) or not chat_id.strip():
        raise ValueError("chat_id is required")
    if not isinstance(message_text, str) or not message_text.strip():
        raise RuntimeError("Message is required")
    if not isinstance(dataset_url, str) or not dataset_url.strip():
        raise RuntimeError("Selected dataset URL is required")

    safe_dataset_name = dataset_name.strip() if isinstance(dataset_name, str) else "Selected dataset"
    if not safe_dataset_name:
        safe_dataset_name = "Selected dataset"

    return chat_id.strip(), message_text.strip(), safe_dataset_name, dataset_url.strip()


async def _emit_streamed_response(
    sio: socketio.AsyncServer,
    sid: str,
    message_id: str,
    chat_id: str,
    response_text: str,
) -> str:
    chunks = [response_text[index : index + STREAM_CHUNK_SIZE] for index in range(0, len(response_text), STREAM_CHUNK_SIZE)]
    if not chunks:
        chunks = [""]
    streamed: list[str] = []
    logger.info(
        "Socket stream started sid=%s message_id=%s chat_id=%s chunks=%s",
        sid,
        message_id,
        chat_id,
        len(chunks),
    )
    for chunk in chunks:
        piece = chunk
        streamed.append(piece)
        await sio.emit(
            "response_chunk",
            {"message_id": message_id, "chat_id": chat_id, "content": piece},
            to=sid,
        )
        await asyncio.sleep(0.04)

    logger.info(
        "Socket stream completed sid=%s message_id=%s chat_id=%s output_len=%s",
        sid,
        message_id,
        chat_id,
        len("".join(streamed).strip()),
    )
    return "".join(streamed).strip()


def register_chat_events(sio: socketio.AsyncServer) -> None:
    @sio.event
    async def connect(sid: str, environ: dict[str, Any], auth: Any) -> bool:
        logger.info("Socket client connected sid=%s", sid)
        return True

    @sio.event
    async def disconnect(sid: str) -> None:
        logger.info("Socket client disconnected sid=%s", sid)
        return None

    @sio.event
    async def message(sid: str, data: dict[str, Any]) -> None:
        message_id = str(uuid.uuid4())
        logger.info("Socket message received sid=%s message_id=%s", sid, message_id)

        try:
            chat_id, message_text, dataset_name, dataset_url = _validate_message_payload(data)
            logger.info(
                "Socket payload validated sid=%s message_id=%s chat_id=%s dataset=%s user_len=%s",
                sid,
                message_id,
                chat_id,
                dataset_name,
                len(message_text),
            )
        except ValueError as exc:
            logger.warning("Socket payload validation failed sid=%s message_id=%s error=%s", sid, message_id, str(exc))
            await sio.emit(
                "query_error",
                {"message_id": message_id, "message": str(exc)},
                to=sid,
            )
            return
        except RuntimeError as exc:
            logger.warning("Socket payload validation failed sid=%s message_id=%s error=%s", sid, message_id, str(exc))
            await sio.emit(
                "query_error",
                {"message_id": message_id, "message": str(exc)},
                to=sid,
            )
            return

        try:
            logger.info("Socket phase=load_chat sid=%s message_id=%s chat_id=%s", sid, message_id, chat_id)
            chat = await asyncio.to_thread(get_chat, chat_id)
            if not chat:
                raise ValueError("Chat not found")
            logger.info("Socket phase=load_chat completed sid=%s message_id=%s", sid, message_id)

            await sio.emit("query_started", {"message_id": message_id, "chat_id": chat_id}, to=sid)
            await sio.emit(
                "thinking",
                {
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "status": f"Loading schema for {dataset_name}",
                },
                to=sid,
            )

            logger.info("Socket phase=fetch_dataset_schema sid=%s message_id=%s url=%s", sid, message_id, dataset_url)
            dataset_schema = await asyncio.to_thread(fetch_dataset_schema, dataset_url)
            logger.info(
                "Socket phase=fetch_dataset_schema completed sid=%s message_id=%s schema_keys=%s",
                sid,
                message_id,
                list(dataset_schema.keys()),
            )

            await sio.emit(
                "thinking",
                {"message_id": message_id, "chat_id": chat_id, "status": "Generating response with LLM"},
                to=sid,
            )

            logger.info("Socket phase=generate_llm sid=%s message_id=%s", sid, message_id)
            response_text = await asyncio.to_thread(
                generate_chat_response,
                chat.get("messages", []),
                message_text,
                dataset_name,
                dataset_schema,
            )

            try:
                parsed_response = json.loads(response_text)
                if isinstance(parsed_response, dict) and isinstance(parsed_response.get("error"), str):
                    error_message = parsed_response["error"]
                    logger.warning(
                        "Socket phase=generate_llm returned error payload sid=%s message_id=%s error=%s",
                        sid,
                        message_id,
                        error_message,
                    )
                    await asyncio.to_thread(
                        append_chat_message,
                        chat_id,
                        message_text,
                        error_message,
                    )
                    await sio.emit(
                        "query_error",
                        {
                            "message_id": message_id,
                            "chat_id": chat_id,
                            "message": error_message,
                        },
                        to=sid,
                    )
                    return
            except json.JSONDecodeError:
                pass

            logger.info(
                "Socket phase=generate_llm completed sid=%s message_id=%s response_len=%s",
                sid,
                message_id,
                len(response_text),
            )
            streamed_response = await _emit_streamed_response(
                sio=sio,
                sid=sid,
                message_id=message_id,
                chat_id=chat_id,
                response_text=response_text,
            )

            logger.info("Socket phase=append_chat_message sid=%s message_id=%s", sid, message_id)
            saved_message = await asyncio.to_thread(
                append_chat_message,
                chat_id,
                message_text,
                streamed_response,
            )
            logger.info(
                "Socket phase=append_chat_message completed sid=%s message_id=%s timestamp=%s",
                sid,
                message_id,
                saved_message.get("timestamp"),
            )
            await sio.emit(
                "query_complete",
                {
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "response": streamed_response,
                    "timestamp": saved_message["timestamp"],
                },
                to=sid,
            )
            logger.info("Socket message completed sid=%s message_id=%s", sid, message_id)
        except Exception as exc:
            logger.exception(
                "Socket message failed sid=%s message_id=%s chat_id=%s",
                sid,
                message_id,
                chat_id,
            )
            await sio.emit(
                "query_error",
                {
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "message": _resolve_error_message(exc),
                },
                to=sid,
            )
