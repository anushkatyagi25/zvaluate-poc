from urllib.parse import urlparse

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from core.config import MONGO_DB_NAME, MONGO_URI
from core.logging_config import get_logger

logger = get_logger(__name__)

_client: MongoClient | None = None
_DEFAULT_SELECTION_TIMEOUT_MS = 5000


def _redact_uri(uri: str) -> str:
    parsed = urlparse(uri)
    host = parsed.hostname or "unknown-host"
    scheme = parsed.scheme or "mongodb"
    return f"{scheme}://{host}"


def _get_client() -> MongoClient:
    global _client
    if _client is not None:
        return _client

    if not MONGO_URI:
        logger.error("MongoDB client initialization failed missing MONGO_URI")
        raise RuntimeError("MONGO_URI is not set")

    try:
        candidate = MongoClient(MONGO_URI, serverSelectionTimeoutMS=_DEFAULT_SELECTION_TIMEOUT_MS)
        candidate.admin.command("ping")
        _client = candidate
        logger.info("MongoDB client initialized default_db=%s host=%s", MONGO_DB_NAME, _redact_uri(MONGO_URI))
    except PyMongoError as exc:
        logger.exception("MongoDB client initialization failed host=%s", _redact_uri(MONGO_URI))
        raise RuntimeError(
            "Unable to connect to MongoDB. Check MONGO_URI, DNS/network access, and MongoDB IP allowlist."
        ) from exc

    return _client


def get_db() -> Database:
    return _get_client()[MONGO_DB_NAME]


def get_named_db(db_name: str) -> Database:
    return _get_client()[db_name]
