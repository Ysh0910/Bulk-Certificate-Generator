from celery import Celery

from app.config import settings

celery_app = Celery(
    "cert_generator",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks"],
)

# Celery reliability settings:
# - task_acks_late=True: Acknowledge task only AFTER execution finishes so worker crashes do not drop tasks.
# - task_reject_on_worker_lost=True: Requeue tasks if worker process is abruptly killed/terminated.
# - worker_prefetch_multiplier=1: Fair dispatch across workers; prevents a single worker from hoarding tasks.
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.CELERY_ALWAYS_EAGER,
    task_eager_propagates=settings.CELERY_ALWAYS_EAGER,
)

# Alias for celery CLI entrypoint
app = celery_app
