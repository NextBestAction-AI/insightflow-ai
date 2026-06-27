"""
backend/services/llm/usage_tracker.py
=======================================
Request-level and aggregate usage accounting for LLM calls.

Tracks
------
* Request count (total / successful / failed)
* Token usage (prompt, completion, total)
* Estimated cost (using configurable price tables)
* Latency (per-request and aggregate)
* Cache hits / misses

Design notes
------------
* **Async-safe** — all mutations are guarded by ``asyncio.Lock``.
* **In-memory only** — this class is the authoritative source during the
  process lifetime.  Persist snapshots to the database in a background task
  if durable accounting is required.
* **Provider-agnostic cost table** — add pricing for new models by updating
  ``_COST_PER_1K_TOKENS``; the tracker itself has no provider knowledge.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cost table (USD per 1 000 tokens)
# ---------------------------------------------------------------------------
# Update these values when provider pricing changes.

_COST_PER_1K_TOKENS: dict[str, dict[str, float]] = {
    # Gemini
    "gemini-1.5-pro":   {"prompt": 0.00125, "completion": 0.00500},
    "gemini-1.5-flash": {"prompt": 0.000075, "completion": 0.000300},
    "gemini-1.0-pro":   {"prompt": 0.000125, "completion": 0.000375},
    # OpenAI
    "gpt-4o":           {"prompt": 0.00500, "completion": 0.01500},
    "gpt-4o-mini":      {"prompt": 0.000150, "completion": 0.000600},
    "gpt-4-turbo":      {"prompt": 0.01000, "completion": 0.03000},
    "gpt-3.5-turbo":    {"prompt": 0.000500, "completion": 0.001500},
}

_DEFAULT_COST: dict[str, float] = {"prompt": 0.0, "completion": 0.0}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class UsageRecord:
    """
    Metrics for a single LLM request.

    Populated by :meth:`UsageTracker.record` and stored in the aggregate.
    """

    model: str
    provider: str
    prompt_tokens: int
    output_tokens: int
    latency_ms: float
    success: bool
    from_cache: bool
    estimated_cost_usd: float
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UsageStats:
    """Aggregate usage statistics snapshot."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0

    total_cost_usd: float = 0.0

    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        """Fraction of requests that succeeded."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of requests served from cache."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


# ---------------------------------------------------------------------------
# UsageTracker
# ---------------------------------------------------------------------------

class UsageTracker:
    """
    Thread-safe, in-memory LLM usage accounting.

    Parameters
    ----------
    max_records:
        Maximum number of individual :class:`UsageRecord` objects to retain
        in the history buffer.  When the buffer is full the oldest record is
        discarded.  Set to ``0`` to disable history storage.
    """

    def __init__(self, max_records: int = 10_000) -> None:
        self._max_records = max_records
        self._lock = asyncio.Lock()

        # Aggregate counters (never reset between requests)
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0

        self._total_prompt_tokens = 0
        self._total_output_tokens = 0
        self._total_cost_usd = 0.0

        self._total_latency_ms = 0.0
        self._min_latency_ms: float = float("inf")
        self._max_latency_ms: float = 0.0

        # Rolling history (capped at max_records)
        self._history: list[UsageRecord] = []

        logger.info(
            "UsageTracker initialised — max_records=%d", max_records
        )

    # ── Public write API ────────────────────────────────────────────────────

    async def record(
        self,
        *,
        model: str,
        provider: str,
        prompt_tokens: int,
        output_tokens: int,
        latency_ms: float,
        success: bool,
        from_cache: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> UsageRecord:
        """
        Record the outcome of a single LLM request.

        Parameters
        ----------
        model:           Exact model name used (e.g. ``"gemini-1.5-pro"``).
        provider:        Provider identifier string (e.g. ``"gemini"``).
        prompt_tokens:   Tokens consumed by the prompt (``-1`` if unknown).
        output_tokens:   Tokens in the completion (``-1`` if unknown).
        latency_ms:      Wall-clock time from send to response in ms.
        success:         Whether the request completed without error.
        from_cache:      Whether the response was served from the cache.
        metadata:        Arbitrary key-value pairs for auditing.

        Returns
        -------
        UsageRecord
            The record that was stored.
        """
        cost = self._estimate_cost(model, prompt_tokens, output_tokens)

        record = UsageRecord(
            model=model,
            provider=provider,
            prompt_tokens=max(prompt_tokens, 0),
            output_tokens=max(output_tokens, 0),
            latency_ms=latency_ms,
            success=success,
            from_cache=from_cache,
            estimated_cost_usd=cost,
            metadata=metadata or {},
        )

        async with self._lock:
            self._total_requests += 1
            if success:
                self._successful_requests += 1
            else:
                self._failed_requests += 1

            if from_cache:
                self._cache_hits += 1
            else:
                self._cache_misses += 1

            if prompt_tokens > 0:
                self._total_prompt_tokens += prompt_tokens
            if output_tokens > 0:
                self._total_output_tokens += output_tokens

            self._total_cost_usd += cost
            self._total_latency_ms += latency_ms
            self._min_latency_ms = min(self._min_latency_ms, latency_ms)
            self._max_latency_ms = max(self._max_latency_ms, latency_ms)

            # Maintain capped history
            if self._max_records > 0:
                if len(self._history) >= self._max_records:
                    self._history.pop(0)
                self._history.append(record)

        logger.debug(
            "Usage recorded — model=%s success=%s tokens=%d+%d cost=$%.6f latency=%.1fms",
            model,
            success,
            max(prompt_tokens, 0),
            max(output_tokens, 0),
            cost,
            latency_ms,
        )
        return record

    # ── Public read API ─────────────────────────────────────────────────────

    async def get_stats(self) -> UsageStats:
        """
        Return a point-in-time snapshot of aggregate usage statistics.

        Returns
        -------
        UsageStats
        """
        async with self._lock:
            avg = (
                self._total_latency_ms / self._total_requests
                if self._total_requests > 0
                else 0.0
            )
            return UsageStats(
                total_requests=self._total_requests,
                successful_requests=self._successful_requests,
                failed_requests=self._failed_requests,
                cache_hits=self._cache_hits,
                cache_misses=self._cache_misses,
                total_prompt_tokens=self._total_prompt_tokens,
                total_output_tokens=self._total_output_tokens,
                total_tokens=self._total_prompt_tokens + self._total_output_tokens,
                total_cost_usd=round(self._total_cost_usd, 6),
                total_latency_ms=self._total_latency_ms,
                avg_latency_ms=round(avg, 2),
                min_latency_ms=(
                    self._min_latency_ms
                    if self._min_latency_ms != float("inf")
                    else 0.0
                ),
                max_latency_ms=self._max_latency_ms,
            )

    async def get_history(
        self,
        limit: int = 100,
        provider: str | None = None,
        model: str | None = None,
    ) -> list[UsageRecord]:
        """
        Return recent usage records, optionally filtered.

        Parameters
        ----------
        limit:      Maximum number of records to return (most recent first).
        provider:   If set, only include records from this provider.
        model:      If set, only include records for this model.

        Returns
        -------
        list[UsageRecord]
        """
        async with self._lock:
            records = list(reversed(self._history))

        if provider:
            records = [r for r in records if r.provider == provider]
        if model:
            records = [r for r in records if r.model == model]

        return records[:limit]

    async def reset(self) -> None:
        """Reset all counters and clear history."""
        async with self._lock:
            self._total_requests = 0
            self._successful_requests = 0
            self._failed_requests = 0
            self._cache_hits = 0
            self._cache_misses = 0
            self._total_prompt_tokens = 0
            self._total_output_tokens = 0
            self._total_cost_usd = 0.0
            self._total_latency_ms = 0.0
            self._min_latency_ms = float("inf")
            self._max_latency_ms = 0.0
            self._history.clear()
        logger.info("UsageTracker reset.")

    # ── Private helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _estimate_cost(model: str, prompt_tokens: int, output_tokens: int) -> float:
        """
        Estimate the USD cost of a single request.

        Uses the price table in ``_COST_PER_1K_TOKENS``.  Unknown models
        return 0.0 with a warning.

        Parameters
        ----------
        model:          Model name (exact match required against price table).
        prompt_tokens:  Number of prompt tokens (``-1`` treated as ``0``).
        output_tokens:  Number of completion tokens (``-1`` treated as ``0``).

        Returns
        -------
        float
            Estimated cost in USD.
        """
        pricing = _COST_PER_1K_TOKENS.get(model)
        if pricing is None:
            logger.debug(
                "No pricing data for model '%s' — cost estimated as $0.00.", model
            )
            pricing = _DEFAULT_COST

        p_tokens = max(prompt_tokens, 0)
        o_tokens = max(output_tokens, 0)
        cost = (p_tokens / 1000) * pricing["prompt"] + (
            o_tokens / 1000
        ) * pricing["completion"]
        return cost
