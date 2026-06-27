"""
backend/services/llm/retry_handler.py
=======================================
Provider-agnostic retry executor with exponential back-off.

Design decisions
----------------
* **No provider-specific code** — the handler operates on any awaitable
  callable; it knows nothing about Gemini, OpenAI, or any other SDK.
* **Configurable per-call** — callers may override ``max_retries``,
  ``base_delay``, and ``max_delay`` on each invocation.
* **Selective retry** — only retries on exception types listed in
  ``retryable_exceptions``; non-transient errors propagate immediately.
* **Jitter** — adds a small random offset to back-off intervals to
  prevent the thundering-herd problem.
* **Structured logging** — every attempt and outcome is logged.

Default retryable exceptions (configured in :class:`RetryHandler.__init__`)
  • :class:`LLMRateLimitError`
  • :class:`LLMTimeoutError`
  • :class:`LLMProviderError`  (excludes auth errors which are never transient)
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from backend.services.llm.exceptions import (
    LLMProviderError,
    LLMRateLimitError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")  # Return type of the wrapped callable


class RetryHandler:
    """
    Wraps an async callable with exponential back-off retry logic.

    Parameters
    ----------
    max_retries:
        Total number of additional attempts after the first failure.
        ``0`` means no retries (the callable is executed exactly once).
    base_delay:
        Initial back-off delay in seconds (doubled after each attempt).
    max_delay:
        Upper cap on the back-off delay in seconds.
    jitter:
        If ``True`` (default), adds up to 20 % random jitter to each
        delay interval to reduce thundering-herd effects.
    retryable_exceptions:
        Tuple of exception *types* that should trigger a retry.
        Any other exception propagates immediately without retry.

    Usage
    -----
        handler = RetryHandler(max_retries=3, base_delay=1.0, max_delay=30.0)
        result = await handler.execute(my_async_fn, arg1, kwarg=value)
    """

    #: Default set of exception types considered transient / retryable.
    DEFAULT_RETRYABLE: tuple[type[Exception], ...] = (
        LLMRateLimitError,
        LLMTimeoutError,
        LLMProviderError,
    )

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0.")
        if base_delay <= 0:
            raise ValueError("base_delay must be > 0.")
        if max_delay < base_delay:
            raise ValueError("max_delay must be >= base_delay.")

        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._jitter = jitter
        self._retryable = (
            retryable_exceptions
            if retryable_exceptions is not None
            else self.DEFAULT_RETRYABLE
        )

        logger.info(
            "RetryHandler configured — max_retries=%d base_delay=%.1fs max_delay=%.1fs",
            max_retries,
            base_delay,
            max_delay,
        )

    # ── Public API ──────────────────────────────────────────────────────────

    async def execute(
        self,
        fn: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Call ``fn(*args, **kwargs)`` with retry logic applied.

        Parameters
        ----------
        fn:
            An async callable (coroutine function) to execute.
        *args, **kwargs:
            Passed through to ``fn`` on every attempt.

        Returns
        -------
        T
            The return value of the first successful call.

        Raises
        ------
        LLMRetryExhaustedError
            If all ``max_retries + 1`` attempts raise a retryable exception.
        Exception
            Re-raised immediately if the exception is *not* in
            ``retryable_exceptions``.
        """
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                logger.debug(
                    "RetryHandler attempt %d/%d — fn=%s",
                    attempt + 1,
                    self._max_retries + 1,
                    getattr(fn, "__name__", repr(fn)),
                )
                result: T = await fn(*args, **kwargs)
                if attempt > 0:
                    logger.info(
                        "Call succeeded on attempt %d/%d.",
                        attempt + 1,
                        self._max_retries + 1,
                    )
                return result

            except tuple(self._retryable) as exc:  # type: ignore[misc]
                last_exc = exc
                if attempt == self._max_retries:
                    # No more attempts remaining — fall through to raise below
                    break

                delay = self._compute_delay(attempt)
                logger.warning(
                    "Retryable error on attempt %d/%d — %s: %s. "
                    "Retrying in %.2fs …",
                    attempt + 1,
                    self._max_retries + 1,
                    type(exc).__name__,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

            except Exception as exc:
                # Non-retryable: propagate immediately
                logger.error(
                    "Non-retryable error on attempt %d/%d — %s: %s. Aborting.",
                    attempt + 1,
                    self._max_retries + 1,
                    type(exc).__name__,
                    exc,
                )
                raise

        # All retry attempts exhausted
        raise LLMRetryExhaustedError(
            f"All {self._max_retries + 1} attempt(s) failed for "
            f"'{getattr(fn, '__name__', repr(fn))}'.",
            attempts=self._max_retries + 1,
            last_error=last_exc,
            details={
                "max_retries": self._max_retries,
                "last_error_type": type(last_exc).__name__ if last_exc else None,
                "last_error_msg": str(last_exc) if last_exc else None,
            },
        )

    # ── Private helpers ─────────────────────────────────────────────────────

    def _compute_delay(self, attempt: int) -> float:
        """
        Compute the back-off delay for the given (0-indexed) attempt number.

        Formula: ``min(base * 2^attempt, max_delay) ± jitter``

        Parameters
        ----------
        attempt:    Zero-based attempt index (0 = first retry).

        Returns
        -------
        float
            Delay in seconds, never exceeding ``self._max_delay``.
        """
        delay = min(self._base_delay * (2 ** attempt), self._max_delay)
        if self._jitter:
            # Add ± 10 % random jitter
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)
        return max(delay, 0.0)
