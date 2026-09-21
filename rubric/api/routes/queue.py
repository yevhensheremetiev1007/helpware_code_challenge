from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from rubric.api.deps import current_tenant, get_db
from rubric.api.schemas import QueueItem
from rubric.db import repositories
from rubric.db.models import Tenant

router = APIRouter(prefix="/v1", tags=["queue"])


@router.get("/queue", response_model=list[QueueItem])
async def review_queue(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    """Scored conversations waiting for a supervisor to review them.

    This endpoint does not call the model.
    """
    return repositories.list_review_queue(db, tenant.id, limit, offset)
