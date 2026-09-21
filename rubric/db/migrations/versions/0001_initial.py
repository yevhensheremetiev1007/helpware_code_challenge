"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("webhook_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "conversations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False, server_default="chat"),
        sa.Column("closed_at", TS, nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_conv_external"),
    )
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    op.create_index("ix_conversations_closed_at", "conversations", ["closed_at"])

    op.create_table(
        "rubrics",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("active_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_rubrics_tenant_id", "rubrics", ["tenant_id"])

    op.create_table(
        "rubric_versions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("rubric_id", UUID, sa.ForeignKey("rubrics.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False, server_default="system"),
        sa.UniqueConstraint("rubric_id", "version", name="uq_rubric_version"),
    )
    op.create_index("ix_rubric_versions_rubric_id", "rubric_versions", ["rubric_id"])

    op.create_table(
        "rubric_categories",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("rubric_version_id", UUID, sa.ForeignKey("rubric_versions.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("weight", sa.Numeric(5, 2), nullable=False, server_default="1"),
        sa.Column("scoring_instructions", sa.Text(), nullable=False),
    )
    op.create_index("ix_rubric_categories_version", "rubric_categories", ["rubric_version_id"])

    op.create_table(
        "scoring_jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("conversation_id", UUID, sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("rubric_version_id", UUID, sa.ForeignKey("rubric_versions.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scoring_jobs_tenant_id", "scoring_jobs", ["tenant_id"])
    op.create_index("ix_scoring_jobs_conversation_id", "scoring_jobs", ["conversation_id"])

    op.create_table(
        "scores",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("conversation_id", UUID, sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("rubric_version_id", UUID, sa.ForeignKey("rubric_versions.id"), nullable=False),
        sa.Column("job_id", UUID, nullable=True),
        sa.Column("total", sa.Numeric(6, 2), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scores_tenant_id", "scores", ["tenant_id"])
    op.create_index("ix_scores_conversation_id", "scores", ["conversation_id"])
    op.create_index("ix_scores_created_at", "scores", ["created_at"])

    op.create_table(
        "category_scores",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("score_id", UUID, sa.ForeignKey("scores.id"), nullable=False),
        sa.Column("rubric_category_id", UUID, sa.ForeignKey("rubric_categories.id"), nullable=False),
        sa.Column("value", sa.Numeric(6, 2), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
    )
    op.create_index("ix_category_scores_score_id", "category_scores", ["score_id"])

    op.create_table(
        "score_reviews",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("score_id", UUID, sa.ForeignKey("scores.id"), nullable=False),
        sa.Column("reviewer_id", sa.String(120), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_score_reviews_score_id", "score_reviews", ["score_id"])


def downgrade() -> None:
    for table in (
        "score_reviews",
        "category_scores",
        "scores",
        "scoring_jobs",
        "rubric_categories",
        "rubric_versions",
        "rubrics",
        "conversations",
        "tenants",
    ):
        op.drop_table(table)
