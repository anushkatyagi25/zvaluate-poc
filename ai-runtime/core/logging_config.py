import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.config import LOG_BACKUP_COUNT, LOG_FILE_PATH, LOG_LEVEL, LOG_MAX_BYTES


def _resolve_level(level_name: str) -> int:
    return getattr(logging, level_name.upper(), logging.INFO)


def configure_logging() -> None:
    log_file = Path(LOG_FILE_PATH)
    if not log_file.is_absolute():
        log_file = Path(__file__).resolve().parent.parent / log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=_resolve_level(LOG_LEVEL),
        handlers=[stream_handler, file_handler],
        force=True,
    )

    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured level=%s file=%s max_bytes=%s backup_count=%s",
        LOG_LEVEL,
        str(log_file),
        LOG_MAX_BYTES,
        LOG_BACKUP_COUNT,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
