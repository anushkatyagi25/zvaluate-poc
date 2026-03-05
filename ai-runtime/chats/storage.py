from datetime import datetime, timezone
from typing import Any

from pymongo import DESCENDING
from pymongo.database import Database

from core.logging_config import get_logger

CHAT_COLLECTION = "chats"
logger = get_logger(__name__)


def ensure_chat_collection(db: Database) -> None:
    logger.info("Ensuring chat collection name=%s", CHAT_COLLECTION)
    existing_collections = db.list_collection_names()
    if CHAT_COLLECTION not in existing_collections:
        db.create_collection(CHAT_COLLECTION)
        logger.info("Chat collection created name=%s", CHAT_COLLECTION)

    collection = db[CHAT_COLLECTION]
    collection.create_index([("updated_at", DESCENDING)], name="updated_at_desc_idx")
    logger.info("Chat collection index ensured index=updated_at_desc_idx")


def build_new_chat_document(user_id: str | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "user_id": user_id,
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }


def build_chat_message(user_message: str, llm_response: str) -> dict[str, Any]:
    return {
        "user_message": user_message,
        "llm_response": llm_response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
