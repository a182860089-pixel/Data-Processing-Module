import asyncio
import logging
from typing import Any, Dict
from celery import states
from app.services.queue.celery_app import celery_app
from app.services.conversion.conversion_service import ConversionService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="convert_pdf_to_markdown")
def convert_pdf_to_markdown(self, file_path: str, filename: str, options: Dict[str, Any] | None = None):
    """Celery task: convert a file to Markdown using existing ConversionService."""
    options = options or {}
    service = ConversionService()
    try:
        self.update_state(state="PROGRESS", meta={"step": "started"})
        result = asyncio.run(service.convert(file_path, filename, options))
        self.update_state(state="PROGRESS", meta={"step": "saving"})
        return result
    except Exception as exc:  # pragma: no cover - Celery worker path
        logger.exception("Celery task failed: %s", exc)
        self.update_state(state=states.FAILURE, meta={"error": str(exc)})
        raise

