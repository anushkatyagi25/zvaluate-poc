import asyncio

from fastapi import FastAPI

from chats.storage import ensure_chat_collection
from core.database import get_db


def register_lifecycle_events(fastapi_app: FastAPI) -> None:
    @fastapi_app.on_event("startup")
    async def on_startup() -> None:
        await asyncio.to_thread(ensure_chat_collection, get_db())
