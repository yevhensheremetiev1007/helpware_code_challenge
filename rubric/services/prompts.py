"""Prompt construction for conversation scoring."""

import hashlib

from rubric.db.models import Conversation, RubricVersion

TEMPLATE = """You are a quality assurance reviewer for a customer support team.

Score the conversation below against each category. For each category return a
value from 0 to 100 and one sentence of justification.

Categories:
{categories}

Conversation transcript:
{transcript}

Return JSON only.
"""


def build_scoring_prompt(conversation: Conversation, version: RubricVersion) -> str:
    category_names = {c.name for c in version.categories}
    instructions_by_name = {c.name: c.scoring_instructions for c in version.categories}

    lines = []
    for name in category_names:
        lines.append(f"- {name}: {instructions_by_name[name]}")

    return TEMPLATE.format(
        categories="\n".join(lines),
        transcript=conversation.transcript,
    )


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
