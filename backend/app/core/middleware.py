import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request

from app.core.metrics import observe_http_request


LOGGER = logging.getLogger("app.request")
SKIP_LOG_PATHS = {"/health", "/metrics"}


def setup_request_logging_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        start = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_seconds = time.perf_counter() - start
            path = _path_template(request)
            observe_http_request(
                method=request.method,
                path=path,
                status_code=status_code,
                duration_seconds=duration_seconds,
            )

            if request.url.path not in SKIP_LOG_PATHS:
                LOGGER.info(
                    "http_request",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": round(duration_seconds * 1000, 2),
                        "client_host": request.client.host if request.client else None,
                    },
                )

            if "response" in locals():
                response.headers["X-Request-ID"] = request_id


def _path_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path
