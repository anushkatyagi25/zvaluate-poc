from typing import Any

from core.config import ARGUS_DATASETS_COLLECTION, ARGUS_DB_NAME
from core.database import get_named_db
from core.logging_config import get_logger

logger = get_logger(__name__)


def _build_dataset_name(document: dict[str, Any]) -> str:
    for candidate_field in ("name", "title", "dataset_name", "display_name"):
        value = document.get(candidate_field)
        if isinstance(value, str) and value.strip():
            return value.strip()

    url = document.get("url")
    if isinstance(url, str) and url.strip():
        url_segments = [segment for segment in url.rstrip("/").split("/") if segment]
        if url_segments:
            return url_segments[-1]
        return url

    return str(document.get("_id", "Unnamed dataset"))


def list_datasets() -> list[dict[str, str]]:
    logger.info(
        "Repository list_datasets started db=%s collection=%s",
        ARGUS_DB_NAME,
        ARGUS_DATASETS_COLLECTION,
    )
    db = get_named_db(ARGUS_DB_NAME)
    cursor = db[ARGUS_DATASETS_COLLECTION].find(
        {},
        {
            "_id": 1,
            "name": 1,
            "title": 1,
            "dataset_name": 1,
            "display_name": 1,
            "url": 1,
        },
    )

    datasets: list[dict[str, str]] = []
    for document in cursor:
        url = document.get("url")
        datasets.append(
            {
                "id": str(document.get("_id", "")),
                "name": _build_dataset_name(document),
                "url": url.strip() if isinstance(url, str) else "",
            }
        )

    datasets.sort(key=lambda item: item["name"].lower())
    logger.info("Repository list_datasets completed count=%s", len(datasets))
    return datasets
