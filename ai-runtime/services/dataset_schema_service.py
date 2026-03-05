import csv
import io
import json
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from core.logging_config import get_logger

MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024
CSV_SAMPLE_ROWS = 50
logger = get_logger(__name__)


def _looks_like_int(value: str) -> bool:
    try:
        int(value)
        return True
    except ValueError:
        return False


def _looks_like_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _infer_scalar_type(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return "null"
    lowered = trimmed.lower()
    if lowered in {"true", "false"}:
        return "boolean"
    if _looks_like_int(trimmed):
        return "integer"
    if _looks_like_float(trimmed):
        return "number"
    return "string"


def _combine_types(existing: str, incoming: str) -> str:
    if existing == incoming:
        return existing
    if existing == "null":
        return incoming
    if incoming == "null":
        return existing
    if {existing, incoming} == {"integer", "number"}:
        return "number"
    return "string"


def _parse_csv_schema(content: bytes) -> dict[str, Any]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    inferred: dict[str, str] = {header: "null" for header in headers}
    row_count = 0

    for row in reader:
        row_count += 1
        if row_count > CSV_SAMPLE_ROWS:
            break
        for header in headers:
            value = row.get(header, "")
            value_type = _infer_scalar_type("" if value is None else str(value))
            inferred[header] = _combine_types(inferred[header], value_type)

    return {
        "format": "csv",
        "columns": [{"name": header, "type": inferred[header]} for header in headers],
        "sample_rows": row_count,
    }


def _json_value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _parse_json_schema(content: bytes) -> dict[str, Any]:
    payload = json.loads(content.decode("utf-8", errors="replace"))

    if isinstance(payload, dict):
        return {
            "format": "json",
            "root_type": "object",
            "fields": [{"name": key, "type": _json_value_type(value)} for key, value in payload.items()],
        }

    if isinstance(payload, list):
        item_type = "null"
        object_fields: dict[str, str] = {}
        sample_count = 0

        for item in payload[:CSV_SAMPLE_ROWS]:
            sample_count += 1
            this_type = _json_value_type(item)
            item_type = _combine_types(item_type, this_type)
            if isinstance(item, dict):
                for key, value in item.items():
                    value_type = _json_value_type(value)
                    object_fields[key] = _combine_types(object_fields.get(key, "null"), value_type)

        schema: dict[str, Any] = {
            "format": "json",
            "root_type": "array",
            "items_type": item_type,
            "sample_items": sample_count,
        }
        if object_fields:
            schema["fields"] = [{"name": key, "type": object_fields[key]} for key in sorted(object_fields.keys())]
        return schema

    return {"format": "json", "root_type": _json_value_type(payload)}


def fetch_dataset_schema(dataset_url: str) -> dict[str, Any]:
    logger.info("Dataset schema fetch started url=%s", dataset_url)
    parsed = urlparse(dataset_url)
    if parsed.scheme not in {"http", "https"}:
        logger.warning("Dataset schema fetch failed invalid scheme url=%s", dataset_url)
        raise ValueError("Dataset URL must be an http(s) link")

    with urlopen(dataset_url, timeout=20) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        content = response.read(MAX_DOWNLOAD_BYTES)
    logger.info(
        "Dataset downloaded bytes=%s content_type=%s path=%s",
        len(content),
        content_type,
        parsed.path,
    )

    path = parsed.path.lower()
    is_csv = path.endswith(".csv") or "text/csv" in content_type or "application/csv" in content_type
    is_json = path.endswith(".json") or "application/json" in content_type or "text/json" in content_type

    if is_csv:
        schema = _parse_csv_schema(content)
        logger.info("Dataset schema parsed format=csv columns=%s", len(schema.get("columns", [])))
        return schema
    if is_json:
        schema = _parse_json_schema(content)
        logger.info("Dataset schema parsed format=json")
        return schema

    try:
        schema = _parse_csv_schema(content)
        logger.info("Dataset schema parsed via fallback format=csv columns=%s", len(schema.get("columns", [])))
        return schema
    except Exception:
        try:
            schema = _parse_json_schema(content)
            logger.info("Dataset schema parsed via fallback format=json")
            return schema
        except Exception as exc:
            logger.exception("Dataset schema fetch failed unsupported format url=%s", dataset_url)
            raise ValueError("Unsupported dataset format. Expected CSV or JSON.") from exc
