"""Unit tests for the scoring service, with the model call replaced."""

import uuid

import pytest

from rubric.db import repositories
from rubric.services import prompts, scoring

SAMPLE_RESPONSE = {
    "categories": {
        "Greeting": {"value": 80.0, "weight": 1, "justification": "Greeted by name."},
    },
    "usage": {"input_tokens": 120, "output_tokens": 18},
}


def test_prompt_contains_every_category(db, tenant, conversation):
    rubric = repositories.get_default_rubric(db, tenant.id)
    version = repositories.get_active_rubric_version(db, tenant.id, rubric.id)

    prompt = prompts.build_scoring_prompt(conversation, version)

    assert "Greeting" in prompt
    assert "Agent: Hello, this is Sam." in prompt


def test_parse_model_response_averages_the_categories():
    parsed = scoring.parse_model_response(SAMPLE_RESPONSE)

    assert parsed["total"] == 80.0
    assert parsed["categories"]["Greeting"]["justification"] == "Greeted by name."


def test_scoring_writes_a_score_and_its_categories(db, tenant, conversation, fake_model):
    rubric = repositories.get_default_rubric(db, tenant.id)

    score = scoring.score_conversation_sync(db, tenant.id, conversation.id, rubric.id)

    assert float(score.total) == 80.0
    assert score.conversation_id == conversation.id

    stored = repositories.list_scores_for_conversation(db, tenant.id, conversation.id)
    assert len(stored) == 1


def test_scoring_an_unknown_conversation_raises(db, tenant):
    rubric = repositories.get_default_rubric(db, tenant.id)

    with pytest.raises(scoring.ScoringError):
        scoring.score_conversation_sync(db, tenant.id, uuid.uuid4(), rubric.id)
