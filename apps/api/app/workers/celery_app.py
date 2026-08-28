"""Celery application.

Task modules (script/asset/video/stitch/payment) are registered in later
phases via the `include` list. For now this boots a healthy, idle worker.
"""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "primo",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.video_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
