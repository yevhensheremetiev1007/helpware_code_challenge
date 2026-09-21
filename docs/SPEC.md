# Rubric — service specification

Version 0.4. Written before the first release. Some parts are out of date.

## 1. Purpose

Score completed support conversations against a per-tenant quality rubric, and
show the results to supervisors in a review queue where they can accept,
override, or dispute a score.

## 2. Users and how they reach the service

| User | Path | What they expect |
|---|---|---|
| Supervisor | React dashboard | Opens a review queue, selects a conversation, reads the score and the model's justification for each category. Can ask for an immediate re-score after editing a rubric. |
| Client integration | REST API | Client helpdesks send each conversation to us over a webhook when it closes. Traffic is uneven. Four of our six tenants are integrated this way. |
| Nightly job | Scheduled task | A reconciliation pass. It scores anything closed in the previous 24 hours that does not already have a current score. It covers the two tenants without a webhook integration, and it catches anything the webhook path missed or dropped. |
| QA analyst | React dashboard | A calibration view that compares model scores against human scores for the same conversation. |

## 3. Scale

- **6 tenants** today. Contracts signed for 20 by the end of the year.
- **About 40,000 conversations per day** in total. Volume is uneven: the
  largest tenant is 60 percent of it.
- **Nightly batch window: 02:00 to 06:00 UTC.** Everything from the previous
  day must be scored before supervisors start work.
- **Webhook traffic is uneven.** It reaches about 400 conversations per minute
  for five to ten minutes when a large tenant's shift ends.
- **Interactive re-score:** when a supervisor asks for a re-score, they should
  get a result, or at least clear feedback that it is in progress, within a few
  seconds. They should not have to wait behind the nightly batch if they are
  working late.
- **Model latency is fixed.** A scoring call takes 2 to 12 seconds depending on
  the length of the transcript. This will not improve.
- **Model quota.** The platform team tells us we have 200 requests per minute
  and 400,000 tokens per minute for this model in this region. Raising it is a
  conversation with AWS that takes several weeks.

## 4. Requirements that are not about features

- **Tenant isolation.** A tenant must never see another tenant's data. The
  tenant is taken from the authenticated caller, never from a field in the
  request body.
- **One authoritative score.** A conversation scored against a given rubric
  version should end with one authoritative score. This must hold however many
  times the conversation is submitted, retried, or picked up by the nightly
  reconciliation pass. A re-score after a rubric change is a new rubric
  version, and both scores are kept for audit.
- **Scores do not change after they are written.** An agent's pay may depend on
  a score, and a supervisor may already have reviewed it. Corrections are made
  by adding a new record, never by overwriting an existing one.
- **Cost matters.** Model spend is the largest line in this service's budget.
  Every model call must be attributable to a tenant and to a purpose.
- **Audit.** For any score, we must be able to say which rubric version, which
  model, and which prompt produced it.
- **Fail clearly.** If the model is not available, the service should say so and
  keep the work. It must not drop the work silently, and it must not report
  success.
- **Observability.** An on-call engineer should be able to answer "what is
  happening right now, for which tenant, and is it getting better or worse"
  from telemetry alone. They should not need to read the application code or
  query the production database.

## 5. Out of scope

Authentication (a stub supplies the tenant), the rubric editing screen, cloud
infrastructure code, and CI/CD pipelines.

**Also out of scope: the wording of the prompt and the accuracy of the scores.**
We are not asking anyone to make the scores better or the prompt smarter.

**In scope, because people often assume otherwise:** how the model is called,
and what we record about each call; queue and worker configuration; and the
frontend, to the extent that API changes affect what a supervisor sees.

## 6. API

```
POST   /v1/conversations/{conversation_id}/score
       Submit one conversation for scoring against the tenant's active rubric.
       Body:   { "rubric_id": "uuid", "priority": "interactive" | "batch" }
       Header: Idempotency-Key (optional, supplied by the caller)
       Interactive submissions must not wait behind batch work.

POST   /v1/batches
       Submit many conversations at once. Used by the nightly job.
       Body: { "rubric_id": "uuid", "conversation_ids": ["uuid", ...] }
       Should accept the set, record durably that each one needs scoring, and
       return immediately.

POST   /v1/webhooks/conversation-closed
       Called by a client helpdesk when a conversation closes.
       Body: { "external_id", "channel", "closed_at", "transcript" }

GET    /v1/jobs/{job_id}
       The state of one scoring job.
       -> { job_id, status: queued|running|succeeded|failed, score_id?, error? }

GET    /v1/conversations/{conversation_id}/scores
       Every score kept for this conversation, newest first, one per rubric
       version.

POST   /v1/rubrics
GET    /v1/rubrics/{rubric_id}
       Rubric management. A rubric is a set of weighted categories, each with
       its own scoring instructions. Editing a rubric creates a new version.

GET    /v1/queue
       The supervisor review queue: scored conversations waiting for review,
       with filters and pagination.

GET    /health
       Liveness and readiness. The load balancer calls this every 10 seconds
       and removes a container from service after 3 failures in a row.
```

## 7. Data model

```
tenants(id, slug, name, webhook_enabled, created_at)

conversations(id, tenant_id, external_id, channel, closed_at, transcript)

rubrics(id, tenant_id, name, active_version)
rubric_versions(id, rubric_id, version, created_at, created_by)
rubric_categories(id, rubric_version_id, name, weight, scoring_instructions)

scoring_jobs(id, tenant_id, conversation_id, rubric_version_id,
             idempotency_key, status, attempts, error, created_at, updated_at)

scores(id, tenant_id, conversation_id, rubric_version_id, job_id,
       total, model_id, prompt_hash, created_at)

category_scores(id, score_id, rubric_category_id, value, justification,
                tokens_used)

score_reviews(id, score_id, reviewer_id, decision, note, created_at)
```

Every tenant-scoped table carries `tenant_id`. Every score links to the exact
`rubric_version_id` and records `model_id` and `prompt_hash` for audit.
