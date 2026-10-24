"""Small async retry helper with exponential backoff."""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")
log = logging.getLogger(__name__)


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    label: str = "call",
) -> T:
    """Run `fn` up to `attempts` times, backing off between failures. Re-raises the last error."""
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 - we deliberately retry on anything
            last_exc = exc
            if attempt == attempts:
                break
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.2)
            log.warning("%s failed (attempt %d/%d): %s; retrying in %.1fs",
                        label, attempt, attempts, exc, delay)
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
