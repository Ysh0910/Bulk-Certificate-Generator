from celery import Celery

from app.config import settings

celery_app = Celery(
    "cert_generator",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_always_eager=settings.CELERY_ALWAYS_EAGER,
    task_eager_propagates=settings.CELERY_ALWAYS_EAGER,
)

# Alias for celery CLI entrypoint
app = celery_app
