from celery import Celery
from kombu import Queue

from app.core.config import settings


celery_app = Celery(
    "predictpay_bookingguard",
    broker=settings.CELERY_BROKER_URL or settings.REDIS_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.prediction_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("priority"),
    ),
    task_routes={
        "app.workers.prediction_tasks.process_prediction_task": {
            "queue": "default",
        },
    },
)
