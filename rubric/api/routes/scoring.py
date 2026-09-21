import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from rubric.api.deps import current_tenant, get_db
from rubric.api.schemas import BatchRequest, JobOut, ScoreOut, ScoreRequest
from rubric.db import repositories
from rubric.db.base import SessionLocal
from rubric.db.models import Tenant
from rubric.services import scoring

router = APIRouter(prefix="/v1", tags=["scoring"])

# The default thread pool was too small and the nightly batch was not finishing
# inside the window, so we run batch work on our own larger pool. -- day 4
_BATCH_POOL = ThreadPoolExecutor(max_workers=128, thread_name_prefix="batch")


def _resolve_rubric_id(db: Session, tenant: Tenant, rubric_id: uuid.UUID | None) -> uuid.UUID:
    if rubric_id is not None:
        return rubric_id
    rubric = repositories.get_default_rubric(db, tenant.id)
    if rubric is None:
        raise HTTPException(status_code=400, detail="tenant has no rubric")
    return rubric.id


@router.post("/conversations/{conversation_id}/score", response_model=ScoreOut)
async def submit_score(
    conversation_id: uuid.UUID,
    body: ScoreRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    """Score one conversation and return the result."""
    rubric_id = _resolve_rubric_id(db, tenant, body.rubric_id)
    try:
        return await scoring.score_conversation(db, tenant.id, conversation_id, rubric_id)
    except scoring.ScoringError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/batches", status_code=202)
async def submit_batch(
    body: BatchRequest,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    """Accept a set of conversations for scoring.

    Used by the nightly job. Returns as soon as the work has been started.
    """
    rubric_id = _resolve_rubric_id(db, tenant, body.rubric_id)

    loop = asyncio.get_running_loop()
    for conversation_id in body.conversation_ids:
        loop.run_in_executor(_BATCH_POOL, _score_one, tenant.id, conversation_id, rubric_id)

    return {"accepted": len(body.conversation_ids)}


def _score_one(tenant_id: uuid.UUID, conversation_id: uuid.UUID, rubric_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        scoring.score_conversation_sync(db, tenant_id, conversation_id, rubric_id)
    except Exception as exc:  # noqa: BLE001
        print(f"batch item failed: {exc}")
    finally:
        db.close()


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    raise HTTPException(status_code=501, detail="not implemented")
