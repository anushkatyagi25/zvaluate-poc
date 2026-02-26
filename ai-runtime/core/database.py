from pymongo import MongoClient
from pymongo.database import Database

from core.config import MONGO_DB_NAME, MONGO_URI

if not MONGO_URI:
    raise ValueError("MONGO_URI is not set")

_client = MongoClient(MONGO_URI)
_db = _client[MONGO_DB_NAME]


def get_db() -> Database:
    return _db


def get_named_db(db_name: str) -> Database:
    return _client[db_name]
