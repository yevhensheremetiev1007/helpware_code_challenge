import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from rubric.api.deps import current_tenant, get_db
from rubric.api.schemas import WebhookPayload
from rubric.db import repositories
from rubric.db.models import Conversation, Tenant
from rubric.services import scoring

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/conversation-closed", status_code=202)
async def conversation_closed(
    payload: WebhookPayload,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    """Called by a client helpdesk when a conversation closes.

    Stores the conversation and scores it straight away so that supervisors see
    the result in the review queue as soon as they log on.
    """
    conversation = repositories.get_conversation_by_external_id(db, tenant.id, payload.external_id)
    if conversation is None:
        conversation = Conversation(
            tenant_id=tenant.id,
            external_id=payload.external_id,
            channel=payload.channel,
            closed_at=payload.closed_at,
            transcript=payload.transcript,
        )
        db.add(conversation)
        db.commit()

    rubric = repositories.get_default_rubric(db, tenant.id)
    if rubric is None:
        raise HTTPException(status_code=400, detail="tenant has no rubric")

    score = await scoring.score_conversation(db, tenant.id, conversation.id, rubric.id)
    return {"conversation_id": str(conversation.id), "score_id": str(score.id)}
