import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException

from chats.repository import create_chat, delete_chat, get_chat, list_chats
from core.logging_config import get_logger
from repositories.datasets_repository import list_datasets

logger = get_logger(__name__)


def register_routes(fastapi_app: FastAPI) -> None:
    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:
        logger.info("Health check requested")
        return {"status": "ok"}

    @fastapi_app.post("/api/chats")
    async def create_chat_session() -> dict[str, Any]:
        logger.info("Create chat requested")
        chat = await asyncio.to_thread(create_chat, None)
        logger.info("Create chat completed chat_id=%s", chat.get("chat_id"))
        return {"chat": chat}

    @fastapi_app.get("/api/chats")
    async def get_chat_sessions() -> dict[str, Any]:
        logger.info("List chats requested")
        chats = await asyncio.to_thread(list_chats)
        logger.info("List chats completed count=%s", len(chats))
        return {"chats": chats}

    @fastapi_app.get("/api/chats/{chat_id}")
    async def get_chat_session(chat_id: str) -> dict[str, Any]:
        logger.info("Get chat requested chat_id=%s", chat_id)
        try:
            chat = await asyncio.to_thread(get_chat, chat_id)
        except ValueError as exc:
            logger.warning("Get chat failed invalid chat_id=%s error=%s", chat_id, str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if not chat:
            logger.warning("Get chat failed not found chat_id=%s", chat_id)
            raise HTTPException(status_code=404, detail="Chat not found")
        logger.info("Get chat completed chat_id=%s message_count=%s", chat_id, len(chat.get("messages", [])))
        return {"chat": chat}

    @fastapi_app.delete("/api/chats/{chat_id}")
    async def delete_chat_session(chat_id: str) -> dict[str, Any]:
        logger.info("Delete chat requested chat_id=%s", chat_id)
        try:
            deleted = await asyncio.to_thread(delete_chat, chat_id)
        except ValueError as exc:
            logger.warning("Delete chat failed invalid chat_id=%s error=%s", chat_id, str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if not deleted:
            logger.warning("Delete chat failed not found chat_id=%s", chat_id)
            raise HTTPException(status_code=404, detail="Chat not found")

        logger.info("Delete chat completed chat_id=%s", chat_id)
        return {"deleted": True, "chat_id": chat_id}

    @fastapi_app.get("/datasets")
    async def get_datasets() -> dict[str, list[dict[str, str]]]:
        logger.info("List datasets requested")
        records = await asyncio.to_thread(list_datasets)
        logger.info("List datasets completed count=%s", len(records))
        return {"datasets": records}
