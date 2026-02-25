from typing import Any

from core.database import get_db
from schemas.chat_history_schema import CHAT_HISTORY_COLLECTION, build_chat_history_document


def insert_chat_history(message_id: str, user_prompt: str, llm_response: str) -> Any:
    db = get_db()
    document = build_chat_history_document(
        message_id=message_id,
        user_prompt=user_prompt,
        llm_response=llm_response,
    )
    return db[CHAT_HISTORY_COLLECTION].insert_one(document)
