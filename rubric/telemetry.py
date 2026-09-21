"""Metrics.

These four are what the dashboard is built on.
"""

from prometheus_client import Counter

requests_total = Counter(
    "rubric_requests_total",
    "HTTP requests handled",
)

scores_created_total = Counter(
    "rubric_scores_created_total",
    "Scores written to the database",
)

errors_total = Counter(
    "rubric_errors_total",
    "Unhandled errors raised inside the application",
)
