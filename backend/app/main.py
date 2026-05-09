from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.metrics import metrics_response
from app.core.middleware import setup_request_logging_middleware


configure_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
)

setup_request_logging_middleware(app)

app.include_router(api_router)


@app.get("/metrics", include_in_schema=False)
def metrics():
    return metrics_response()
