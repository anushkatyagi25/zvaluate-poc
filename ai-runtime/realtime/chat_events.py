import asyncio
import uuid
from typing import Any

import socketio

from chats.repository import append_chat_message, get_chat
from services.dataset_schema_service import fetch_dataset_schema
from services.llm_service import LLMConfigurationError, LLMResponseError, generate_chat_response


def _resolve_error_message(exc: Exception) -> str:
    if isinstance(exc, (LLMConfigurationError, LLMResponseError)):
        return str(exc)
    if isinstance(exc, ValueError):
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
    chunks = response_text.split(" ")
    streamed: list[str] = []
    for chunk in chunks:
        piece = f"{chunk} "
        streamed.append(piece)
        await sio.emit(
            "response_chunk",
            {"message_id": message_id, "chat_id": chat_id, "content": piece},
            to=sid,
        )
        await asyncio.sleep(0.04)

    return "".join(streamed).strip()


def register_chat_events(sio: socketio.AsyncServer) -> None:
    @sio.event
    async def connect(sid: str, environ: dict[str, Any], auth: Any) -> bool:
        return True

    @sio.event
    async def disconnect(sid: str) -> None:
        return None

    @sio.event
    async def message(sid: str, data: dict[str, Any]) -> None:
        message_id = str(uuid.uuid4())

        try:
            chat_id, message_text, dataset_name, dataset_url = _validate_message_payload(data)
        except ValueError as exc:
            await sio.emit(
                "query_error",
                {"message_id": message_id, "message": str(exc)},
                to=sid,
            )
            return
        except RuntimeError as exc:
            await sio.emit(
                "query_error",
                {"message_id": message_id, "message": str(exc)},
                to=sid,
            )
            return

        try:
            chat = await asyncio.to_thread(get_chat, chat_id)
            if not chat:
                raise ValueError("Chat not found")

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

            dataset_schema = await asyncio.to_thread(fetch_dataset_schema, dataset_url)
            # Schema is intentionally fetched and validated here; prompt integration will be added later.
            _ = dataset_schema

            await sio.emit(
                "thinking",
                {"message_id": message_id, "chat_id": chat_id, "status": "Generating response with LLM"},
                to=sid,
            )

            response_text = await asyncio.to_thread(
                generate_chat_response,
                chat.get("messages", []),
                message_text,
            )
            streamed_response = await _emit_streamed_response(
                sio=sio,
                sid=sid,
                message_id=message_id,
                chat_id=chat_id,
                response_text=response_text,
            )

            saved_message = await asyncio.to_thread(
                append_chat_message,
                chat_id,
                message_text,
                streamed_response,
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
        except Exception as exc:
            await sio.emit(
                "query_error",
                {
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "message": _resolve_error_message(exc),
                },
                to=sid,
            )
