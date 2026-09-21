from typing import Iterator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from rubric.db import repositories
from rubric.db.base import SessionLocal
from rubric.db.models import Tenant


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_tenant(
    x_tenant_slug: str = Header(..., alias="X-Tenant-Slug"),
    db: Session = Depends(get_db),
) -> Tenant:
    """Stand-in for the real authentication layer.

    In production the tenant comes from the authenticated principal. Here it
    comes from a header so that the stack can run without an identity provider.
    Everything downstream of this function is the same in both cases.
    """
    tenant = repositories.get_tenant_by_slug(db, x_tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=401, detail="unknown tenant")
    return tenant
