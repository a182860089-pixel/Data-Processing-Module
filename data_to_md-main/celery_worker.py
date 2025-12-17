from app.services.queue.celery_app import celery_app

# Entry point for running Celery worker:
# celery -A celery_worker.celery_app worker -l info -P solo (Windows)

if __name__ == "__main__":
    celery_app.start()

