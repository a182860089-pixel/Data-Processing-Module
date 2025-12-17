import logging
from celery import Celery
from app.config import get_settings

logger = logging.getLogger(__name__)


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    settings = get_settings()

    celery = Celery(
        "data_to_md",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.services.queue.tasks"],
    )

    celery.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        worker_concurrency=settings.max_concurrent_pdf_tasks,
        task_soft_time_limit=settings.celery_task_soft_time_limit,
        task_time_limit=settings.celery_task_hard_time_limit,
        broker_connection_retry_on_startup=True,
    )

    logger.info(
        "Celery app initialized with broker=%s, backend=%s, concurrency=%s",
        settings.celery_broker_url,
        settings.celery_result_backend,
        settings.max_concurrent_pdf_tasks,
    )
    return celery


celery_app = create_celery_app()

