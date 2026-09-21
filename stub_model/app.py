"""Stub scoring model.

Stands in for Amazon Bedrock so that the stack runs with no AWS account. It
copies the three behaviours that matter for this service:

  1. Latency between STUB_LATENCY_MIN and STUB_LATENCY_MAX seconds.
  2. A requests-per-minute quota. Over the quota it returns 429, which the
     client turns into a ThrottlingException. Production quota for this model
     is 200 requests per minute; STUB_RPM is scaled down to match the scaled
     down seed data.
  3. Occasional read timeouts. The stub sleeps past the client timeout instead
     of answering. Note that the work is still done, and in production it would
     still be billed.

Sampling: if the request does not set a temperature, Anthropic models default
to 1.0 and the output varies between calls. This stub does the same. If the
request sets temperature to 0 the output is derived from the prompt alone, so
the same prompt gives the same answer.
"""

import hashlib
import json
import os
import random
import re
import threading
import time
from collections import deque

import anyio.to_thread
from fastapi import Body, FastAPI, Response

RPM = int(os.getenv("STUB_RPM", "40"))
LATENCY_MIN = float(os.getenv("STUB_LATENCY_MIN", "2.0"))
LATENCY_MAX = float(os.getenv("STUB_LATENCY_MAX", "12.0"))
TIMEOUT_RATE = float(os.getenv("STUB_TIMEOUT_RATE", "0.04"))

app = FastAPI(title="stub-model")

_lock = threading.Lock()
_calls: deque[float] = deque()
_stats = {"served": 0, "throttled": 0, "timed_out": 0}

CATEGORY_RE = re.compile(r"^- (?P<name>[^:]+):", re.MULTILINE)


def _over_quota() -> bool:
    now = time.monotonic()
    with _lock:
        while _calls and now - _calls[0] > 60:
            _calls.popleft()
        if len(_calls) >= RPM:
            return True
        _calls.append(now)
        return False


def _score_for(name: str, prompt: str, temperature: float | None) -> float:
    seed = hashlib.sha256(f"{name}|{prompt}".encode()).hexdigest()
    base = 55 + (int(seed[:8], 16) % 40)
    if temperature is not None and temperature == 0:
        return float(base)
    # Sampling is on. The same prompt gives a different answer each time.
    return float(max(0, min(100, base + random.randint(-6, 6))))


@app.on_event("startup")
async def widen_threadpool() -> None:
    # The handler below is synchronous so that many calls can be in flight at
    # once. The default limit of 40 would make the stub the bottleneck instead
    # of the quota.
    anyio.to_thread.current_default_thread_limiter().total_tokens = 1024


@app.get("/_stub/health")
async def health():
    return {"status": "ok", "rpm_limit": RPM, **_stats}


@app.post("/model/{model_id:path}/invoke")
def invoke(model_id: str, payload: dict = Body(...)):
    prompt = payload["messages"][0]["content"]
    temperature = payload.get("temperature")

    if _over_quota():
        _stats["throttled"] += 1
        return Response(
            status_code=429,
            content=json.dumps({"message": "Too many requests"}),
            media_type="application/json",
        )

    latency = random.uniform(LATENCY_MIN, LATENCY_MAX)

    if random.random() < TIMEOUT_RATE:
        # The model keeps working. The caller gives up first.
        _stats["timed_out"] += 1
        time.sleep(latency + 45)
    else:
        time.sleep(latency)

    names = CATEGORY_RE.findall(prompt) or ["Overall"]
    categories = {}
    prompt_tokens = max(1, len(prompt) // 4)
    completion_tokens = 0

    for name in names:
        name = name.strip()
        value = _score_for(name, prompt, temperature)
        justification = f"The agent scored {value:.0f} on {name.lower()}."
        completion_tokens += max(1, len(justification) // 4)
        categories[name] = {
            "value": value,
            "weight": 1,
            "justification": justification,
        }

    _stats["served"] += 1
    return {
        "model_id": model_id,
        "categories": categories,
        "usage": {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
        },
    }
