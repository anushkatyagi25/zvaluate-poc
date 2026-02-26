import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException

from chats.repository import create_chat, get_chat, list_chats
from repositories.datasets_repository import list_datasets


def register_routes(fastapi_app: FastAPI) -> None:
    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @fastapi_app.post("/api/chats")
    async def create_chat_session() -> dict[str, Any]:
        chat = await asyncio.to_thread(create_chat, None)
        return {"chat": chat}

    @fastapi_app.get("/api/chats")
    async def get_chat_sessions() -> dict[str, Any]:
        chats = await asyncio.to_thread(list_chats)
        return {"chats": chats}

    @fastapi_app.get("/api/chats/{chat_id}")
    async def get_chat_session(chat_id: str) -> dict[str, Any]:
        try:
            chat = await asyncio.to_thread(get_chat, chat_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        return {"chat": chat}

    @fastapi_app.get("/datasets")
    async def get_datasets() -> dict[str, list[dict[str, str]]]:
        records = await asyncio.to_thread(list_datasets)
        return {"datasets": records}
