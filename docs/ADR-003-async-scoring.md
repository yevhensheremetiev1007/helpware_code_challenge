# ADR-003: Scoring is an asynchronous job, not a request

- **Status:** Accepted
- **Date:** 2026-07-02
- **Authors:** S. Okafor, with review from the platform team
- **Supersedes:** none

## Context

A scoring call to the model takes between 2 and 12 seconds. It fails sometimes.
It costs money every time it runs. Volume is about 40,000 conversations a day
and is contracted to grow. Most of that volume arrives in two shapes: a burst
of webhook traffic when a large tenant's shift ends, and one large batch
overnight.

Our model quota is 200 requests per minute for this model in this region.
Raising it takes several weeks. The nightly batch needs about 167 requests per
minute sustained to finish 40,000 conversations inside the four hour window, so
we are already close to the limit. The webhook peak of 400 per minute is above
the limit on its own.

Three options were considered.

**Option A: score inside the HTTP request.** The caller waits for the model and
receives the score in the response. Simple to build and simple to reason about.
Rejected: the load balancer idle timeout is 30 seconds, our p99 model latency
is 12 seconds, and any queueing at all pushes us past the timeout. It also
means the caller owns the lifetime of a long operation over a connection that
can drop, which guarantees that callers will resubmit.

**Option B: score in a background task inside the API process.** Quick to
build. Rejected: work held in process memory is lost on deploy, on crash, and
on scale-in, with no record of what was in flight. There is no retry, no dead
letter path, no backpressure, and no way to see how deep the backlog is. It
also cannot be scaled separately from the API.

**Option C: score in a worker, driven by a durable queue.** More moving parts.
Accepted.

## Decision

Submission and execution are separated.

1. `POST /v1/conversations/{id}/score` creates a **scoring job** row and
   returns **202 Accepted** with the job id and a `Location` header. It does
   not call the model.

2. The job row carries an **idempotency key**. The key is either supplied by
   the caller in an `Idempotency-Key` header, or derived from
   `(tenant_id, conversation_id, rubric_version_id)`. There is a unique
   constraint on `(tenant_id, idempotency_key)`. Submitting the same work twice
   returns the existing job rather than creating a second one.

3. A message is published to **SQS**. Interactive and batch work use separate
   queues with separate concurrency budgets, so that a supervisor asking for a
   re-score at 03:00 does not wait behind 40,000 batch messages.

4. A **worker** consumes the queue, calls the model, and writes the score. The
   worker is deployed separately from the API and scales separately.

5. Delivery is at least once, so the worker must be safe to run twice on the
   same message. The score table has a unique constraint on
   `(tenant_id, conversation_id, rubric_version_id)`. The insert is
   first-writer-wins. We never update a score in place, because a score may
   already have been reviewed and an agent's pay may depend on it.

6. Concurrency against the model is **bounded**, derived from the quota and the
   observed latency. At 200 requests per minute and 6 second average latency
   that is roughly 20 calls in flight. Retries use exponential backoff with
   jitter, and only retry errors that are worth retrying.

7. Failures after `maxReceiveCount` attempts go to a **dead letter queue**.
   Note that SQS moves the message instead of delivering it, so the worker is
   not invoked for that final attempt and cannot mark the job failed itself.
   Job state is therefore tracked in `scoring_jobs.attempts`, and a separate
   sweep marks stale jobs as failed.

8. `GET /v1/jobs/{job_id}` reports job state. The dashboard polls it.

## Consequences

**Good.** No request holds a connection open while the model works. Cost is
bounded because duplicate submissions do not produce duplicate model calls. The
backlog is visible as queue depth and message age, which gives us something to
alert on. Workers scale independently of the API.

**Bad.** More infrastructure to run and more states to reason about. The
dashboard needs a pending state, which is more frontend work than showing a
spinner. Local development needs a queue, so the compose file grows.

**Risks.** The visibility timeout must be longer than the worst case processing
time, or messages are redelivered while still being processed and we do work
twice. A dead letter queue that nobody watches is a slower way to lose data, so
depth on it must be alerted.

## Implementation notes

The `scoring_jobs` table and the worker in `rubric/workers/consumer.py` were
written as part of this decision. Queue URLs are in `rubric/config.py`.
