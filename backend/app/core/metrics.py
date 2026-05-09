from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

from app.core.config import settings


HTTP_REQUESTS_TOTAL = Counter(
    "predictpay_http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "predictpay_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path", "status_code"],
)

PREDICTIONS_SUBMITTED_TOTAL = Counter(
    "predictpay_predictions_submitted_total",
    "Predictions accepted by the API and queued for Celery execution.",
    ["queue_name", "plan", "status"],
)

for _queue_name, _plan in (("default", "free"), ("priority", "pro"), ("priority", "admin")):
    PREDICTIONS_SUBMITTED_TOTAL.labels(
        queue_name=_queue_name,
        plan=_plan,
        status="queued",
    ).inc(0)

APP_INFO = Gauge(
    "predictpay_app_info",
    "Application information.",
    ["service", "version", "environment"],
)

APP_INFO.labels(
    service=settings.SERVICE_NAME,
    version=settings.VERSION,
    environment=settings.ENVIRONMENT,
).set(1)


def observe_http_request(
    method: str,
    path: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    labels = {
        "method": method,
        "path": path,
        "status_code": str(status_code),
    }
    HTTP_REQUESTS_TOTAL.labels(**labels).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def record_prediction_submitted(queue_name: str, plan: str, status: str = "queued") -> None:
    PREDICTIONS_SUBMITTED_TOTAL.labels(
        queue_name=queue_name,
        plan=plan,
        status=status,
    ).inc()


def metrics_response() -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
