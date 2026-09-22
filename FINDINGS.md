# FINDINGS — VAN-4417

## Fixed

**Duplicate scores and duplicate model calls on resubmit.**
`score_conversation_sync` always called the model and inserted a new `scores` row. There was no uniqueness on `(tenant_id, conversation_id, rubric_version_id)`, so dashboard retries, nginx 504s, `@retry` after a mid-path commit, and batch/webhook overlap all produced multiple scores (pay) and multiple bills (spend).

**Change:** look up an existing score before `bedrock.invoke`; add a unique constraint; on `IntegrityError` return the winning row (first-writer-wins). Lookup also runs at the start of each `@retry` attempt so a prior successful insert does not trigger another model call.

**Assumption:** resubmitting the same conversation against the same active rubric version returns the existing score. A true re-score requires a new rubric version (per SPEC). Left sync scoring on the HTTP path; did not implement ADR-003.

## Priority list (what I would do next)

1. **Stop scoring on the request thread (ADR-003).** Sync model I/O blocks a Uvicorn worker, so `/health` and `/queue` stall when scoring is slow — matches day-9 LB flapping and “one slow request slows the container.” Highest remaining impact; gateway timeouts alone will not fix it.
2. **Tighten `@retry`.** It wraps the whole sync path with no backoff and retries throttling immediately, which multiplies cost and keeps the batch from draining. Retry only the model call, with backoff, and do not retry after a successful score write.
3. **Nightly batch: skip already-scored + progress.** `conversations_closed_since` returns every closed conversation; resubmitting from the start after a deploy re-scores everything. Filter to missing scores and track checkpoints. (Leave full batch redesign for now per README.)
4. **Cost / model telemetry.** Dashboard only tracks request/score/error counts; `usage` tokens are parsed and discarded. Finance’s 3.4× spend is invisible while `scores_created` rises (including duplicates historically). (Leave per README.)
5. **`Idempotency-Key` is accepted and ignored.** Wire it to job uniqueness when async scoring lands.
6. **nginx 30s vs model latency + frontend `retry: 1`.** These amplify duplicate submits; safer once the server is idempotent. (Leave gateway timeout and dashboard per README.)
7. **DB pool vs batch fan-out.** 128 batch threads vs `pool_size=20` per worker feeds timeouts that then trigger retries. Documented; leave with batch/throttling.

## Explicitly not fixed

Gateway timeouts, nightly batch behaviour, model throttling, cost reporting, and the dashboard — as requested. Idempotency on the live sync path is enough for the required tests and for Art’s pay/spend complaints under sequential and concurrent resubmits.
