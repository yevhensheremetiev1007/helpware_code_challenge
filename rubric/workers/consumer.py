"""Queue consumer for scoring jobs.

Written alongside docs/ADR-003-async-scoring.md. Reads scoring messages from
SQS, runs the scoring call, and updates the job row.

Run with:  python -m rubric.workers.consumer
"""

import json
import logging
import signal
import uuid
from types import FrameType

import boto3

from rubric.config import settings
from rubric.db.base import SessionLocal
from rubric.db.models import ScoringJob
from rubric.services import scoring

logger = logging.getLogger(__name__)

_running = True


def _stop(signum: int, frame: FrameType | None) -> None:
    global _running
    _running = False
    logger.info("shutdown requested, finishing current message")


def sqs_client():
    return boto3.client(
        "sqs",
        endpoint_url=settings.aws_endpoint_url,
        region_name=settings.aws_region,
    )


def handle_message(body: dict) -> None:
    job_id = uuid.UUID(body["job_id"])
    db = SessionLocal()
    try:
        job = db.get(ScoringJob, job_id)
        if job is None:
            logger.warning("job %s not found, dropping message", job_id)
            return

        job.status = "running"
        job.attempts = job.attempts + 1
        db.commit()

        try:
            scoring.score_conversation_sync(
                db,
                tenant_id=job.tenant_id,
                conversation_id=job.conversation_id,
                rubric_id=uuid.UUID(body["rubric_id"]),
            )
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error = str(exc)[:2000]
            db.commit()
            raise

        job.status = "succeeded"
        job.error = None
        db.commit()
    finally:
        db.close()


def run() -> None:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    client = sqs_client()
    logger.info("consumer started, polling %s", settings.sqs_queue_url)

    while _running:
        response = client.receive_message(
            QueueUrl=settings.sqs_queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20,
            VisibilityTimeout=settings.sqs_visibility_timeout,
        )
        for message in response.get("Messages", []):
            try:
                handle_message(json.loads(message["Body"]))
            except Exception:  # noqa: BLE001
                logger.exception("message failed, leaving it for redelivery")
                continue

            client.delete_message(
                QueueUrl=settings.sqs_queue_url,
                ReceiptHandle=message["ReceiptHandle"],
            )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
