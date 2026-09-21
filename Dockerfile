FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Four Uvicorn workers per container. Two containers run in docker-compose,
# which matches production.
CMD ["uvicorn", "rubric.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
