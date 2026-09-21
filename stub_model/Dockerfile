FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi==0.115.6 "uvicorn[standard]==0.34.0"

COPY stub_model /app/stub_model

EXPOSE 9000

# One worker, so that the requests-per-minute quota is counted in one place.
# The handler is synchronous and runs on a wide thread pool, so a single worker
# still serves hundreds of calls at once.
CMD ["uvicorn", "stub_model.app:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "1"]
