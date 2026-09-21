from fastapi import APIRouter

from rubric.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "instance": settings.instance_name}
