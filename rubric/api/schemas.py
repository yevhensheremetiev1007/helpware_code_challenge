import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ScoreRequest(BaseModel):
    rubric_id: uuid.UUID | None = None
    priority: Literal["interactive", "batch"] = "interactive"


class BatchRequest(BaseModel):
    rubric_id: uuid.UUID | None = None
    conversation_ids: list[uuid.UUID]


class WebhookPayload(BaseModel):
    """What a client helpdesk posts when a conversation closes."""

    external_id: str
    channel: str = "chat"
    closed_at: datetime
    transcript: str


class CategoryScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rubric_category_id: uuid.UUID
    value: float
    justification: str


class ScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    rubric_version_id: uuid.UUID
    total: float
    model_id: str
    prompt_hash: str
    created_at: datetime


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    status: str
    attempts: int
    error: str | None = None


class QueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    total: float
    created_at: datetime
