from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database

CHAT_HISTORY_COLLECTION = "chat_history"


def ensure_chat_history_schema(db: Database) -> None:
    existing_collections = db.list_collection_names()
    if CHAT_HISTORY_COLLECTION not in existing_collections:
        db.create_collection(CHAT_HISTORY_COLLECTION)

    collection = db[CHAT_HISTORY_COLLECTION]
    collection.create_index([("message_id", ASCENDING)], unique=True, name="message_id_unique_idx")
    collection.create_index([("created_at", DESCENDING)], name="created_at_desc_idx")


def build_chat_history_document(message_id: str, user_prompt: str, llm_response: str) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc)
    return {
        "message_id": message_id,
        "date": created_at.strftime("%Y-%m-%d"),
        "timestamp": created_at.isoformat(),
        "created_at": created_at,
        "user_prompt": user_prompt,
        "llm_response": llm_response,
    }
