import time
import uuid

from fastapi import FastAPI, Request
from starlette.responses import Response

from core.logging_config import get_logger

logger = get_logger(__name__)


def register_http_logging_middleware(fastapi_app: FastAPI) -> None:
    @fastapi_app.middleware("http")
    async def log_http_requests(request: Request, call_next) -> Response:
        request_id = uuid.uuid4().hex[:10]
        start = time.perf_counter()
        client_host = request.client.host if request.client else "unknown"

        logger.info(
            "HTTP request started request_id=%s method=%s path=%s client=%s",
            request_id,
            request.method,
            request.url.path,
            client_host,
        )

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "HTTP request failed request_id=%s method=%s path=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "HTTP request completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
