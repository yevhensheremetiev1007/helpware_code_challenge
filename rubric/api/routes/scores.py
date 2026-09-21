import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rubric.api.deps import current_tenant, get_db
from rubric.api.schemas import ScoreOut
from rubric.db import repositories
from rubric.db.models import Tenant

router = APIRouter(prefix="/v1", tags=["scores"])


@router.get("/conversations/{conversation_id}/scores", response_model=list[ScoreOut])
async def list_scores(
    conversation_id: uuid.UUID,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    """Every score retained for this conversation, newest first."""
    return repositories.list_scores_for_conversation(db, tenant.id, conversation_id)
