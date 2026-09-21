import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from rubric.api.routes import health, queue, rubrics, scores, scoring, webhooks
from rubric.telemetry import errors_total, requests_total

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Rubric", version="0.4.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def count_requests(request: Request, call_next):
    requests_total.inc()
    try:
        return await call_next(request)
    except Exception:
        errors_total.inc()
        raise


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(health.router)
app.include_router(scoring.router)
app.include_router(scores.router)
app.include_router(queue.router)
app.include_router(rubrics.router)
app.include_router(webhooks.router)
