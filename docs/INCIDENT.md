# Incident notes

This is what the on-call engineer left in the incident channel before going on
holiday. It has been tidied slightly. It is not a complete analysis, and some
of the conclusions in it may be wrong.

---

## Ticket VAN-4417

**Reported by:** Art Vandelay, VP Support Operations
**Priority:** P1
**Title:** Rubric does not work and I think it is also lying to me

> Four problems. They may be one problem. I cannot tell.
>
> **One.** When my supervisors press "re-score" they see a spinner and then an
> error. Not every time. Maybe half the time. It is worse in the afternoon. One
> supervisor waited a full minute before it failed. I am told the dashboard
> tries twice.
>
> **Two.** Estrella opened the score history for a conversation, to settle a
> disagreement with an agent, and found **three different scores for the same
> conversation**, all from the same night: 71, 74, and 68. Which one do I show
> the agent? The agent's bonus depends on this number. This is the part that is
> urgent for me.
>
> **Three.** Finance says our model spend so far this month is already **3.4
> times the forecast for the whole month**. Nobody can tell me why. The
> dashboard says everything is fine and volume is normal.
>
> **Four.** The nightly batch finished at 09:40 yesterday, which is after
> everyone starts work. On Tuesday it did not finish at all. Nobody noticed
> until I asked.
>
> The engineering dashboard is green. I do not believe the dashboard.

---

## On-call notes

```
Day 9, 14:20 UTC — Paged on load balancer 5xx rate. Restarted the service.
  Errors cleared for about 20 minutes and then came back. Restarting keeps
  helping temporarily.

Day 9, 14:55 UTC — /health is timing out from time to time but the containers
  are not dying. CPU 11 percent, memory flat. The load balancer is taking
  targets out of service and putting them back in. It moves in and out; it is
  not a hard outage.

Day 9, 15:30 UTC — When one request is slow, other requests on the same
  container are slow too, including /v1/queue, which does not call the model.
  It is not every container at the same time.

Day 10, 02:00 UTC — Nightly batch started. The model began returning
  ThrottlingException within about 90 seconds. Many of them.

Day 10, 02:04 UTC — Throttling rate is still climbing. It is not draining.

Day 10, 03:10 UTC — Deployed an unrelated config change. Batch progress
  appeared to reset. Resubmitted the batch from the beginning, because I had no
  way to tell what had already been done.

Day 10, 09:40 UTC — Batch "completed". The row count in `scores` for that night
  is much higher than the number of conversations closed the previous day.

Day 11 — Raised the database pool from 5 to 20 and the load balancer idle
  timeout from 30s to 120s. The 504s became 120-second 504s. Reverted the
  timeout. Left the pool change in place.
```

---

## Log extract (production, day 9, 14:52 UTC)

```
scoring conversation 4f2a1c
calling bedrock
got response
score saved
scoring conversation 9b8e33
calling bedrock
scoring conversation 1c4d77
calling bedrock
ERROR:rubric.retry:retrying
Traceback (most recent call last):
  File "/app/rubric/services/scoring.py", line 44, in score_conversation_sync
    response = bedrock.invoke(prompt)
  File "/app/rubric/adapters/bedrock.py", line 69, in invoke
    raw = _client.invoke_model(modelId=settings.model_id, body=payload)
  File "/app/rubric/adapters/bedrock.py", line 35, in invoke_model
    raise ReadTimeoutError(endpoint_url=self._endpoint, error=exc) from exc
botocore.exceptions.ReadTimeoutError: Read timeout on endpoint URL: "http://...
scoring conversation 1c4d77
calling bedrock
got response
score saved
got response
score saved
scoring conversation 9b8e33
calling bedrock
```

---

## Metrics

The dashboard has four panels. It is the only telemetry anyone built.

| Panel | Reading during the incident |
|---|---|
| `rubric_requests_total` | Normal |
| `rubric_scores_created_total` | Higher than usual, still rising |
| `rubric_errors_total` | Slightly higher than usual |
| Container CPU and memory | 11 percent CPU, memory flat |

Raw metrics are at `/metrics` on each container.

---

## How the service runs

Four Uvicorn workers per container. Two containers. Both sit behind nginx, which
has a 30 second read timeout and removes a container from service after three
failed requests in ten seconds.

SQLAlchemy is configured with `pool_size=20`, `max_overflow=0`,
`pool_timeout=30`, per worker. This was raised from 5 on day 11 and left in
place. Postgres is on default settings.

The React dashboard uses TanStack Query with `retry: 1`.

---

## Reproducing it locally

The stub model copies the real one: 2 to 12 second latency, a requests per
minute limit, and occasional read timeouts.

```bash
make repro-interactive   # 20 supervisors press "re-score" at once
make repro-batch         # what the nightly job does
make repro-webhook       # what an integrated helpdesk does
make score-report        # what ended up in the database
make health              # ask the load balancer about service health
```

Note that the seed data is about five percent of a production night, and the
stub's rate limit is scaled down to match. See the README for how to increase
both.
