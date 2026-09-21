"""Data access for the scoring flow."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from rubric.db.models import (
    CategoryScore,
    Conversation,
    Rubric,
    RubricCategory,
    RubricVersion,
    Score,
    Tenant,
)


def get_tenant_by_slug(db: Session, slug: str) -> Tenant | None:
    return db.scalar(select(Tenant).where(Tenant.slug == slug))


def get_conversation(db: Session, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
    return db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
        )
    )


def get_conversation_by_external_id(db: Session, tenant_id: uuid.UUID, external_id: str) -> Conversation | None:
    return db.scalar(
        select(Conversation).where(
            Conversation.tenant_id == tenant_id,
            Conversation.external_id == external_id,
        )
    )


def get_active_rubric_version(db: Session, tenant_id: uuid.UUID, rubric_id: uuid.UUID) -> RubricVersion | None:
    rubric = db.scalar(
        select(Rubric).where(Rubric.id == rubric_id, Rubric.tenant_id == tenant_id)
    )
    if rubric is None:
        return None
    return db.scalar(
        select(RubricVersion).where(
            RubricVersion.rubric_id == rubric.id,
            RubricVersion.version == rubric.active_version,
        )
    )


def get_default_rubric(db: Session, tenant_id: uuid.UUID) -> Rubric | None:
    return db.scalar(select(Rubric).where(Rubric.tenant_id == tenant_id).limit(1))


def get_category(db: Session, category_id: uuid.UUID) -> RubricCategory | None:
    return db.get(RubricCategory, category_id)


def create_score(
    db: Session,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    rubric_version_id: uuid.UUID,
    total: float,
    model_id: str,
    prompt_hash: str,
) -> Score:
    score = Score(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        rubric_version_id=rubric_version_id,
        total=total,
        model_id=model_id,
        prompt_hash=prompt_hash,
    )
    db.add(score)
    db.commit()
    return score


def write_category_scores(db: Session, score: Score, version: RubricVersion, parsed: dict) -> None:
    """Write one row per rubric category.

    Called after create_score. Looks each category up by name so that the model
    can return the categories in any order.
    """
    for name, result in parsed["categories"].items():
        category = db.scalar(
            select(RubricCategory).where(
                RubricCategory.rubric_version_id == version.id,
                RubricCategory.name == name,
            )
        )
        if category is None:
            continue
        db.add(
            CategoryScore(
                score_id=score.id,
                rubric_category_id=category.id,
                value=result["value"],
                justification=result["justification"],
            )
        )
    db.commit()


def list_scores_for_conversation(db: Session, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> list[Score]:
    return list(
        db.scalars(
            select(Score)
            .where(Score.tenant_id == tenant_id, Score.conversation_id == conversation_id)
            .order_by(Score.created_at.desc())
        )
    )


def list_review_queue(db: Session, tenant_id: uuid.UUID, limit: int, offset: int) -> list[Score]:
    return list(
        db.scalars(
            select(Score)
            .where(Score.tenant_id == tenant_id)
            .order_by(Score.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def conversations_closed_since(db: Session, tenant_id: uuid.UUID, hours: int = 24) -> list[Conversation]:
    """Everything this tenant closed in the last N hours.

    Used by the nightly job.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.tenant_id == tenant_id, Conversation.closed_at >= cutoff)
            .order_by(Conversation.closed_at)
        )
    )
