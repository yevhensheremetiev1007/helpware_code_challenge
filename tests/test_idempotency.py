"""VAN-4417: one conversation must end up with one authoritative score.

This is the required part of the exercise. Two tests here fail today. Make them
pass, and keep the rest of the suite passing.

They cover two separate things, and both matter:

  1. Resubmitting must not write a second score row. This is Art's complaint
     two, and it is the one affecting agent pay.
  2. Resubmitting must not call the model again. This is Art's complaint three.
     A database constraint alone will stop the duplicate row but still pay for
     the duplicate model call.

Both are marked xfail so that `make test` is green before you start. When your
fix works, delete the markers.

If your fix makes scoring asynchronous, this test will need to change: there
would be no score immediately after the request returns. That is fine. Rewrite
it so it still asserts the same thing -- that one conversation and one rubric
version produce one authoritative score, however many times it is submitted --
and say in FINDINGS.md what you changed and why.
"""

from rubric.db import repositories


def test_resubmitting_a_conversation_does_not_create_a_second_score(
    client, auth, db, tenant, conversation, fake_model
):
    """A supervisor presses Re-score. The response is slow, so the dashboard
    sends the request again. The agent's pay depends on there being one answer.
    """
    body = {"priority": "interactive"}
    url = f"/v1/conversations/{conversation.id}/score"

    first = client.post(url, json=body, headers=auth)
    second = client.post(url, json=body, headers=auth)

    assert first.status_code < 400, first.text
    assert second.status_code < 400, second.text

    scores = repositories.list_scores_for_conversation(db, tenant.id, conversation.id)
    assert len(scores) == 1, (
        f"expected one score, found {len(scores)}: "
        f"{[float(s.total) for s in scores]}"
    )


def test_resubmitting_a_conversation_does_not_call_the_model_again(
    client, auth, conversation, fake_model
):
    """Every model call costs money. The second submission should not pay for
    work we have already done.
    """
    body = {"priority": "interactive"}
    url = f"/v1/conversations/{conversation.id}/score"

    client.post(url, json=body, headers=auth)
    client.post(url, json=body, headers=auth)

    assert fake_model["count"] == 1, (
        f"the model was called {fake_model['count']} times for one conversation"
    )
