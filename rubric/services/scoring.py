"""Scoring orchestration.

Loads the conversation and the active rubric version, builds the prompt, calls
the model, and writes the score.
"""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rubric.adapters import bedrock
from rubric.config import settings
from rubric.db import repositories
from rubric.db.models import Score
from rubric.retry import retry
from rubric.services import prompts
from rubric.telemetry import scores_created_total


class ScoringError(Exception):
    pass


@retry(attempts=3)
def score_conversation_sync(
    db: Session,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    rubric_id: uuid.UUID,
) -> Score:
    print(f"scoring conversation {str(conversation_id)[:6]}")

    conversation = repositories.get_conversation(db, tenant_id, conversation_id)
    if conversation is None:
        raise ScoringError(f"conversation {conversation_id} not found")

    version = repositories.get_active_rubric_version(db, tenant_id, rubric_id)
    if version is None:
        raise ScoringError(f"rubric {rubric_id} not found")

    existing = repositories.get_score_for_conversation_version(
        db, tenant_id, conversation_id, version.id
    )
    if existing is not None:
        return existing

    prompt = prompts.build_scoring_prompt(conversation, version)

    print("calling bedrock")
    response = bedrock.invoke(prompt)
    print("got response")

    parsed = parse_model_response(response)

    try:
        score = repositories.create_score(
            db,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            rubric_version_id=version.id,
            total=parsed["total"],
            model_id=settings.model_id,
            prompt_hash=prompts.prompt_hash(prompt),
        )
    except IntegrityError:
        db.rollback()
        winner = repositories.get_score_for_conversation_version(
            db, tenant_id, conversation_id, version.id
        )
        if winner is None:
            raise
        return winner

    repositories.write_category_scores(db, score, version, parsed)

    scores_created_total.inc()
    print("score saved")
    return score


async def score_conversation(
    db: Session,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    rubric_id: uuid.UUID,
) -> Score:
    return score_conversation_sync(db, tenant_id, conversation_id, rubric_id)


def parse_model_response(response: dict) -> dict:
    categories = {}
    total = 0.0
    weight_total = 0.0
    for name, payload in response["categories"].items():
        categories[name] = {
            "value": payload["value"],
            "justification": payload["justification"],
        }
        total += payload["value"] * payload.get("weight", 1)
        weight_total += payload.get("weight", 1)

    return {
        "total": round(total / weight_total, 2) if weight_total else 0.0,
        "categories": categories,
        "usage": response.get("usage", {}),
    }
