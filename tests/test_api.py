"""Existing test suite.

These pass. They were written when the service was released.
"""

import uuid


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_are_exposed(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "rubric_requests_total" in response.text


def test_queue_requires_a_tenant(client):
    response = client.get("/v1/queue")
    assert response.status_code == 422


def test_queue_rejects_an_unknown_tenant(client):
    response = client.get("/v1/queue", headers={"X-Tenant-Slug": "nobody"})
    assert response.status_code == 401


def test_queue_starts_empty_for_a_new_tenant(client, auth):
    response = client.get("/v1/queue", headers=auth)
    assert response.status_code == 200
    assert response.json() == []


def test_scores_for_an_unknown_conversation_is_empty(client, auth):
    response = client.get(f"/v1/conversations/{uuid.uuid4()}/scores", headers=auth)
    assert response.status_code == 200
    assert response.json() == []


def test_scoring_an_unknown_conversation_is_a_404(client, auth):
    response = client.post(
        f"/v1/conversations/{uuid.uuid4()}/score",
        json={"priority": "interactive"},
        headers=auth,
    )
    assert response.status_code == 404


def test_rubric_lookup_returns_its_categories(client, auth, tenant, db):
    from rubric.db import repositories

    rubric = repositories.get_default_rubric(db, tenant.id)
    response = client.get(f"/v1/rubrics/{rubric.id}", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert [c["name"] for c in body["categories"]] == ["Greeting"]
