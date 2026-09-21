import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from rubric.api.main import app
from rubric.db.base import SessionLocal
from rubric.services import scoring
from rubric.db.models import (
    CategoryScore,
    Conversation,
    Rubric,
    RubricCategory,
    RubricVersion,
    Score,
    ScoreReview,
    ScoringJob,
    Tenant,
)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def tenant(db):
    """A throwaway tenant with one rubric, cleaned up afterwards."""
    slug = f"test-{uuid.uuid4().hex[:8]}"
    tenant = Tenant(slug=slug, name="Test Tenant", webhook_enabled=True)
    db.add(tenant)
    db.flush()

    rubric = Rubric(tenant_id=tenant.id, name="Test rubric", active_version=1)
    db.add(rubric)
    db.flush()

    version = RubricVersion(rubric_id=rubric.id, version=1, created_by="test")
    db.add(version)
    db.flush()

    db.add(
        RubricCategory(
            rubric_version_id=version.id,
            name="Greeting",
            weight=1,
            scoring_instructions="Did the agent greet the customer?",
        )
    )
    db.commit()

    yield tenant

    # Children first: there are no cascades on these foreign keys.
    score_ids = [s.id for s in db.query(Score).filter_by(tenant_id=tenant.id).all()]
    if score_ids:
        db.query(ScoreReview).filter(ScoreReview.score_id.in_(score_ids)).delete(
            synchronize_session=False
        )
        db.query(CategoryScore).filter(CategoryScore.score_id.in_(score_ids)).delete(
            synchronize_session=False
        )
    db.query(Score).filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
    db.query(ScoringJob).filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
    db.query(Conversation).filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
    db.query(RubricCategory).filter_by(rubric_version_id=version.id).delete(
        synchronize_session=False
    )
    db.query(RubricVersion).filter_by(id=version.id).delete(synchronize_session=False)
    db.query(Rubric).filter_by(id=rubric.id).delete(synchronize_session=False)
    db.query(Tenant).filter_by(id=tenant.id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture()
def auth(tenant):
    return {"X-Tenant-Slug": tenant.slug}


@pytest.fixture()
def conversation(db, tenant):
    """One closed conversation belonging to the test tenant.

    The tenant fixture removes it afterwards.
    """
    row = Conversation(
        tenant_id=tenant.id,
        external_id=f"t-{uuid.uuid4().hex[:8]}",
        channel="chat",
        closed_at=datetime.now(timezone.utc),
        transcript="Customer: Hello.\nAgent: Hello, this is Sam.",
    )
    db.add(row)
    db.commit()
    return row


FAKE_MODEL_RESPONSE = {
    "categories": {
        "Greeting": {"value": 80.0, "weight": 1, "justification": "Greeted by name."},
    },
    "usage": {"input_tokens": 120, "output_tokens": 18},
}


@pytest.fixture()
def fake_model(monkeypatch):
    """Replace the model call so tests are fast and deterministic."""
    calls = {"count": 0}

    def _invoke(_prompt):
        calls["count"] += 1
        return FAKE_MODEL_RESPONSE

    monkeypatch.setattr(scoring.bedrock, "invoke", _invoke)
    return calls
