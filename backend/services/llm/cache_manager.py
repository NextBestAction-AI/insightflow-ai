"""
backend/services/llm/cache_manager.py
=======================================
In-memory LLM response cache with TTL and max-size eviction.

Design decisions
----------------
* **Pure in-memory** — no Redis, Memcached, or filesystem dependency.
* **LRU + TTL eviction** — entries are evicted either when the cache
  reaches ``max_size`` (oldest-accessed evicted first) or when the TTL
  for a specific entry expires.
* **Thread-safe** — uses ``asyncio.Lock`` so concurrent coroutines do not
  corrupt the internal state.
* **Cache key** — a SHA-256 hash of the prompt + provider + model, so
  semantically identical requests share a cache entry regardless of object
  identity.
* **Statistics** — hit / miss / eviction counters exposed via
  :meth:`get_stats`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from backend.services.llm.exceptions import LLMCacheError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class _CacheEntry:
    """Single cached response record."""

    value: str           # Raw LLM response text
    created_at: float    # Unix timestamp of insertion
    ttl: int             # Seconds until expiry (0 = never expires)
    hit_count: int = 0   # Number of times this entry was served

    @property
    def is_expired(self) -> bool:
        """Return True if this entry has exceeded its TTL."""
        if self.ttl == 0:
            return False
        return (time.monotonic() - self.created_at) > self.ttl


@dataclass(slots=True)
class CacheStats:
    """Snapshot of cache performance metrics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    current_size: int = 0
    max_size: int = 0
    ttl_seconds: int = 0

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a fraction in [0.0, 1.0]."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# ---------------------------------------------------------------------------
# CacheManager
# ---------------------------------------------------------------------------

class CacheManager:
    """
    LRU in-memory cache for LLM responses with per-entry TTL support.

    Parameters
    ----------
    ttl:        Default TTL in seconds. ``0`` disables expiry.
    max_size:   Maximum number of entries. Oldest-accessed entry is evicted
                when the cache is full.

    Thread safety
    -------------
    All public methods acquire ``self._lock`` (an ``asyncio.Lock``) before
    touching internal state.  The class is safe to use from a single async
    event loop.
    """

    def __init__(self, ttl: int = 3600, max_size: int = 512) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1.")
        if ttl < 0:
            raise ValueError("ttl must be >= 0.")

        self._ttl = ttl
        self._max_size = max_size
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

        logger.info(
            "CacheManager initialised — max_size=%d ttl=%ds",
            max_size,
            ttl,
        )

    # ── Cache key construction ───────────────────────────────────────────────

    @staticmethod
    def build_key(
        prompt: str,
        provider: str,
        model: str,
        *,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """
        Derive a deterministic cache key from the request parameters.

        Parameters
        ----------
        prompt:   Rendered prompt string.
        provider: Provider identifier (e.g. ``"gemini"``).
        model:    Model name string.
        extra:    Optional additional fields (e.g. temperature) that should
                  differentiate cache entries.

        Returns
        -------
        str
            A hex SHA-256 digest (64 chars).
        """
        payload: dict[str, Any] = {
            "prompt": prompt,
            "provider": provider,
            "model": model,
        }
        if extra:
            payload.update(extra)

        serialised = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialised.encode()).hexdigest()

    # ── Public read / write ──────────────────────────────────────────────────

    async def get(self, key: str) -> str | None:
        """
        Retrieve a cached response.

        Parameters
        ----------
        key:    Cache key produced by :meth:`build_key`.

        Returns
        -------
        str | None
            The cached response text, or ``None`` on miss / expiry.
        """
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                logger.debug("Cache MISS — key=%.12s…", key)
                return None

            if entry.is_expired:
                del self._store[key]
                self._expirations += 1
                self._misses += 1
                logger.debug("Cache EXPIRED — key=%.12s…", key)
                return None

            # Move to end (most-recently-used) for LRU ordering
            self._store.move_to_end(key)
            entry.hit_count += 1
            self._hits += 1
            logger.debug("Cache HIT — key=%.12s…", key)
            return entry.value

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """
        Insert or update a cache entry.

        Parameters
        ----------
        key:    Cache key produced by :meth:`build_key`.
        value:  LLM response text to cache.
        ttl:    Override the default TTL for this specific entry.

        Raises
        ------
        LLMCacheError
            If the value is not a string (programming error guard).
        """
        if not isinstance(value, str):
            raise LLMCacheError(
                f"Cache values must be strings; got {type(value).__name__}."
            )

        effective_ttl = ttl if ttl is not None else self._ttl

        async with self._lock:
            # Evict LRU entry if at capacity and key is new
            if key not in self._store and len(self._store) >= self._max_size:
                evicted_key, _ = self._store.popitem(last=False)
                self._evictions += 1
                logger.debug(
                    "Cache eviction (LRU) — evicted=%.12s… new=%.12s…",
                    evicted_key,
                    key,
                )

            self._store[key] = _CacheEntry(
                value=value,
                created_at=time.monotonic(),
                ttl=effective_ttl,
            )
            self._store.move_to_end(key)
            logger.debug(
                "Cache SET — key=%.12s… ttl=%ds", key, effective_ttl
            )

    async def invalidate(self, key: str) -> bool:
        """
        Remove a specific entry from the cache.

        Returns
        -------
        bool
            ``True`` if the key existed and was removed, ``False`` otherwise.
        """
        async with self._lock:
            if key in self._store:
                del self._store[key]
                logger.debug("Cache INVALIDATE — key=%.12s…", key)
                return True
            return False

    async def clear(self) -> None:
        """Evict all entries and reset statistics."""
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            self._hits = self._misses = self._evictions = self._expirations = 0
            logger.info("Cache cleared — removed %d entries.", count)

    # ── Statistics ───────────────────────────────────────────────────────────

    async def get_stats(self) -> CacheStats:
        """
        Return a snapshot of cache performance statistics.

        Returns
        -------
        CacheStats
        """
        async with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                expirations=self._expirations,
                current_size=len(self._store),
                max_size=self._max_size,
                ttl_seconds=self._ttl,
            )
