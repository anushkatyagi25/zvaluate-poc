from pymongo import MongoClient
from pymongo.database import Database

from core.config import MONGO_URI

if not MONGO_URI:
    raise ValueError("MONGO_URI is not set")

_client = MongoClient(MONGO_URI)
_db = _client["zvaluate_db"]


def get_db() -> Database:
    return _db
