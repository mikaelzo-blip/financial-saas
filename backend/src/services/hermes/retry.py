"""Bounded retry policy for non-financial API delivery failures."""
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class HermesApiError(Exception):
    """Safe transport error returned by a Hermes API transport."""

    status_code: int | None = None
    code: str = "TRANSPORT_ERROR"


def is_retryable(error: HermesApiError) -> bool:
    """Only delivery/transient server outcomes may be retried."""
    return error.status_code is None or error.status_code in {408, 429} or error.status_code >= 500


async def retry_submission(operation: Callable[[], Awaitable[T]], *, max_attempts: int = 3) -> T:
    """Retry the same logical API operation; callers preserve the idempotency key."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    for attempt in range(max_attempts):
        try:
            return await operation()
        except HermesApiError as error:
            if not is_retryable(error) or attempt == max_attempts - 1:
                raise
    raise AssertionError("unreachable")
