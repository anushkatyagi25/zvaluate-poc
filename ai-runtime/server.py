import asyncio
import os
import uuid
from typing import Any

import socketio
from dotenv import load_dotenv
from fastapi import FastAPI

from core.database import get_db
from repositories.chat_history_repository import insert_chat_history
from schemas.chat_history_schema import ensure_chat_history_schema

load_dotenv()

PORT = int(os.getenv("PORT", "8001"))
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")

if FRONTEND_ORIGIN.strip() == "*":
    cors_allowed_origins: str | list[str] = "*"
else:
    cors_allowed_origins = [origin.strip() for origin in FRONTEND_ORIGIN.split(",") if origin.strip()]

fastapi_app = FastAPI(title="AI Runtime Socket Server")
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=cors_allowed_origins,
)

app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="socket.io")


@fastapi_app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@fastapi_app.on_event("startup")
async def on_startup() -> None:
    await asyncio.to_thread(ensure_chat_history_schema, get_db())


def _build_response(message: str) -> str:
    return (
        "Thanks for your message. "
        f"You said: {message}. "
        "This is a streamed dummy response from ai-runtime."
    )


@sio.event
async def connect(sid: str, environ: dict[str, Any], auth: Any) -> bool:
    return True


@sio.event
async def disconnect(sid: str) -> None:
    return None


@sio.event
async def message(sid: str, data: dict[str, Any]) -> None:
    message_text = (data or {}).get("message", "")
    if not isinstance(message_text, str) or not message_text.strip():
        await sio.emit(
            "query_error",
            {"message_id": str(uuid.uuid4()), "message": "Message is required"},
            to=sid,
        )
        return

    message_text = message_text.strip()
    message_id = str(uuid.uuid4())

    try:
        await sio.emit("query_started", {"message_id": message_id}, to=sid)
        await sio.emit(
            "thinking",
            {"message_id": message_id, "status": "Processing your query"},
            to=sid,
        )

        full_response = _build_response(message_text)
        chunks = full_response.split(" ")
        streamed = []

        for chunk in chunks:
            piece = f"{chunk} "
            streamed.append(piece)
            await sio.emit(
                "response_chunk",
                {"message_id": message_id, "content": piece},
                to=sid,
            )
            await asyncio.sleep(0.04)

        await sio.emit(
            "query_complete",
            {"message_id": message_id, "response": "".join(streamed).strip()},
            to=sid,
        )
        await asyncio.to_thread(
            insert_chat_history,
            message_id,
            message_text,
            "".join(streamed).strip(),
        )
    except Exception as exc:
        await sio.emit(
            "query_error",
            {"message_id": message_id, "message": str(exc)},
            to=sid,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=True)
