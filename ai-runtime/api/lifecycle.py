import asyncio

from fastapi import FastAPI

from chats.storage import ensure_chat_collection
from core.database import get_db
from core.logging_config import get_logger

logger = get_logger(__name__)


def register_lifecycle_events(fastapi_app: FastAPI) -> None:
    @fastapi_app.on_event("startup")
    async def on_startup() -> None:
        logger.info("Startup phase: ensuring chat collection")
        await asyncio.to_thread(ensure_chat_collection, get_db())
        logger.info("Startup phase completed: chat collection ready")
