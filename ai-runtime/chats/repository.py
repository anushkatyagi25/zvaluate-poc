from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument

from chats.storage import CHAT_COLLECTION, build_chat_message, build_new_chat_document
from core.database import get_db


def _parse_chat_id(chat_id: str) -> ObjectId:
    try:
        return ObjectId(chat_id)
    except (InvalidId, TypeError) as exc:
        raise ValueError("Invalid chat_id") from exc


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _serialize_chat(chat: dict[str, Any]) -> dict[str, Any]:
    messages = chat.get("messages", [])
    serialized_messages = []
    for message in messages:
        serialized_messages.append(
            {
                "user_message": message.get("user_message", ""),
                "llm_response": message.get("llm_response", ""),
                "timestamp": message.get("timestamp"),
            }
        )

    return {
        "chat_id": str(chat["_id"]),
        "user_id": chat.get("user_id"),
        "messages": serialized_messages,
        "created_at": _to_iso(chat.get("created_at")),
        "updated_at": _to_iso(chat.get("updated_at")),
    }


def create_chat(user_id: str | None = None) -> dict[str, Any]:
    db = get_db()
    collection = db[CHAT_COLLECTION]
    document = build_new_chat_document(user_id=user_id)
    inserted = collection.insert_one(document)
    chat = collection.find_one({"_id": inserted.inserted_id})
    if not chat:
        raise RuntimeError("Failed to create chat")
    return _serialize_chat(chat)


def list_chats(limit: int = 100) -> list[dict[str, Any]]:
    db = get_db()
    collection = db[CHAT_COLLECTION]

    chats: list[dict[str, Any]] = []
    cursor = collection.find({}).sort("updated_at", -1).limit(limit)
    for chat in cursor:
        messages = chat.get("messages", [])
        last_message = messages[-1] if messages else {}
        chats.append(
            {
                "chat_id": str(chat["_id"]),
                "user_id": chat.get("user_id"),
                "message_count": len(messages),
                "last_user_message": last_message.get("user_message"),
                "last_llm_response": last_message.get("llm_response"),
                "created_at": _to_iso(chat.get("created_at")),
                "updated_at": _to_iso(chat.get("updated_at")),
            }
        )

    return chats


def get_chat(chat_id: str) -> dict[str, Any] | None:
    db = get_db()
    object_id = _parse_chat_id(chat_id)
    chat = db[CHAT_COLLECTION].find_one({"_id": object_id})
    if not chat:
        return None
    return _serialize_chat(chat)


def append_chat_message(chat_id: str, user_message: str, llm_response: str) -> dict[str, Any]:
    db = get_db()
    object_id = _parse_chat_id(chat_id)
    collection = db[CHAT_COLLECTION]
    message = build_chat_message(
        user_message=user_message,
        llm_response=llm_response,
    )

    now = datetime.now(timezone.utc)
    updated_chat = collection.find_one_and_update(
        {"_id": object_id},
        {
            "$push": {"messages": message},
            "$set": {"updated_at": now},
        },
        return_document=ReturnDocument.AFTER,
    )

    if not updated_chat:
        raise ValueError("Chat not found")

    return {
        "chat_id": str(updated_chat["_id"]),
        "timestamp": message["timestamp"],
        "message": message,
    }
