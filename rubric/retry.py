"""Retry helper.

Added on day 3 of the incident because the model was returning read timeouts
and the scores were not getting written.
"""

import functools
import logging
from typing import Callable, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


def retry(attempts: int = 3) -> Callable:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_error: Exception | None = None
            for _ in range(attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    logger.error("retrying")
            raise last_error  # type: ignore[misc]

        return wrapper

    return decorator
