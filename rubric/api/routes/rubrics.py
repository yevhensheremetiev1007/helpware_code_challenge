import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from rubric.api.deps import current_tenant, get_db
from rubric.db import repositories
from rubric.db.models import Tenant

router = APIRouter(prefix="/v1", tags=["rubrics"])


@router.get("/rubrics/{rubric_id}")
async def get_rubric(
    rubric_id: uuid.UUID,
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    version = repositories.get_active_rubric_version(db, tenant.id, rubric_id)
    if version is None:
        raise HTTPException(status_code=404, detail="rubric not found")

    return {
        "rubric_id": str(rubric_id),
        "version": version.version,
        "categories": [
            {
                "id": str(c.id),
                "name": c.name,
                "weight": float(c.weight),
                "scoring_instructions": c.scoring_instructions,
            }
            for c in version.categories
        ],
    }
