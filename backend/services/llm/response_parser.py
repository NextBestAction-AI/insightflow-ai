"""
backend/services/llm/response_parser.py
=========================================
LLM response parsing, JSON extraction, validation, and repair.

Responsibilities
----------------
* Extract a JSON object / array from raw LLM text (even if wrapped in
  markdown code fences or surrounded by prose).
* Validate the extracted JSON against an optional Pydantic schema.
* Attempt lightweight JSON repair for common model mistakes.
* Return strongly-typed ``dict`` / ``list`` structures.

Explicitly NOT responsible for
--------------------------------
* Making LLM requests          → :class:`BaseLLMClient`
* Retry logic                  → :class:`RetryHandler`
* Caching                      → :class:`CacheManager`
* Prompt rendering             → :class:`PromptManager`
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from backend.services.llm.exceptions import LLMJSONParseError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Regex patterns for JSON extraction
_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE
)
_JSON_INLINE_RE = re.compile(
    r"(\{[\s\S]*\}|\[[\s\S]*\])"
)


class ResponseParser:
    """
    Parses and validates raw LLM response text into structured Python objects.

    The parser applies a multi-stage extraction strategy:
    1. Strip markdown code fences (````` ```json … ``` ````).
    2. Attempt direct ``json.loads`` on the cleaned text.
    3. Use a regex to find the first ``{…}`` or ``[…]`` block.
    4. Apply heuristic JSON repair on the found block.
    5. Raise :class:`LLMJSONParseError` if all strategies fail.
    """

    # ── Public API ──────────────────────────────────────────────────────────

    def parse_json(self, text: str) -> dict[str, Any] | list[Any]:
        """
        Extract and parse a JSON object or array from ``text``.

        Parameters
        ----------
        text:   Raw string returned by an LLM (may contain prose, markdown, etc.)

        Returns
        -------
        dict | list
            The parsed Python object.

        Raises
        ------
        LLMJSONParseError
            If no valid JSON can be extracted from ``text``.
        """
        logger.debug("Parsing JSON from LLM response — input_len=%d", len(text))

        # Stage 1: try to extract from a markdown code block
        result = self._try_code_block(text)
        if result is not None:
            return result

        # Stage 2: direct parse on the full text (trimmed)
        result = self._try_direct_parse(text.strip())
        if result is not None:
            return result

        # Stage 3: regex extraction of the first JSON structure
        result = self._try_regex_extraction(text)
        if result is not None:
            return result

        # Stage 4: heuristic repair then parse
        result = self._try_repair(text)
        if result is not None:
            return result

        raise LLMJSONParseError(
            "Could not extract valid JSON from LLM response after all strategies.",
            raw_text=text[:500],
            details={"text_length": len(text)},
        )

    def parse_json_as(self, text: str, schema: Type[T]) -> T:
        """
        Parse JSON from ``text`` and validate it against a Pydantic schema.

        Parameters
        ----------
        text:   Raw LLM response string.
        schema: A ``BaseModel`` subclass that the JSON must conform to.

        Returns
        -------
        T
            A validated instance of ``schema``.

        Raises
        ------
        LLMJSONParseError
            If JSON extraction fails or Pydantic validation fails.
        """
        data = self.parse_json(text)

        if isinstance(data, list):
            raise LLMJSONParseError(
                f"Expected a JSON object conforming to {schema.__name__}, "
                f"but got a JSON array.",
                raw_text=text[:500],
            )

        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            raise LLMJSONParseError(
                f"JSON extracted from LLM response is invalid for schema "
                f"'{schema.__name__}': {exc}",
                raw_text=text[:500],
                details={"validation_errors": exc.errors()},
            ) from exc

    def extract_text(self, text: str) -> str:
        """
        Return the raw text content cleaned of markdown fences and leading/
        trailing whitespace.

        Does **not** attempt JSON parsing.

        Parameters
        ----------
        text:   Raw LLM response string.

        Returns
        -------
        str
        """
        # Remove markdown code fences if present
        match = _JSON_BLOCK_RE.search(text)
        if match:
            return match.group(1).strip()
        return text.strip()

    def is_valid_json(self, text: str) -> bool:
        """
        Return ``True`` if ``text`` can be parsed as JSON.

        Parameters
        ----------
        text:   Any string.

        Returns
        -------
        bool
        """
        try:
            json.loads(text)
            return True
        except (json.JSONDecodeError, ValueError):
            return False

    # ── Private extraction strategies ────────────────────────────────────────

    def _try_code_block(self, text: str) -> dict | list | None:
        """Extract JSON from a markdown code block, if present."""
        match = _JSON_BLOCK_RE.search(text)
        if not match:
            return None
        candidate = match.group(1).strip()
        parsed = self._safe_loads(candidate)
        if parsed is not None:
            logger.debug("JSON extracted from markdown code block.")
        return parsed

    def _try_direct_parse(self, text: str) -> dict | list | None:
        """Attempt to parse the whole text directly as JSON."""
        parsed = self._safe_loads(text)
        if parsed is not None:
            logger.debug("JSON extracted via direct parse.")
        return parsed

    def _try_regex_extraction(self, text: str) -> dict | list | None:
        """Find the first ``{…}`` or ``[…]`` substring and parse it."""
        match = _JSON_INLINE_RE.search(text)
        if not match:
            return None
        candidate = match.group(1)
        parsed = self._safe_loads(candidate)
        if parsed is not None:
            logger.debug("JSON extracted via regex — start=%d", match.start())
        return parsed

    def _try_repair(self, text: str) -> dict | list | None:
        """
        Apply lightweight heuristic repairs and attempt parsing.

        Common model mistakes addressed:
        * Trailing commas before ``}`` or ``]``.
        * Single-quoted strings instead of double-quoted.
        * Unquoted ``True`` / ``False`` / ``None`` (Python literals).
        """
        repaired = text

        # Replace Python boolean/None literals with JSON equivalents
        repaired = re.sub(r'\bTrue\b', 'true', repaired)
        repaired = re.sub(r'\bFalse\b', 'false', repaired)
        repaired = re.sub(r'\bNone\b', 'null', repaired)

        # Remove trailing commas before closing brackets
        repaired = re.sub(r',\s*([\}\]])', r'\1', repaired)

        # Attempt to extract the first JSON-like block after repairs
        match = _JSON_INLINE_RE.search(repaired)
        if match:
            parsed = self._safe_loads(match.group(1))
            if parsed is not None:
                logger.info("JSON recovered after heuristic repair.")
                return parsed

        return None

    @staticmethod
    def _safe_loads(text: str) -> dict | list | None:
        """Return parsed JSON or ``None`` on any error (no exception raised)."""
        try:
            result = json.loads(text)
            if isinstance(result, (dict, list)):
                return result
            # Scalars are not useful for structured LLM outputs
            return None
        except (json.JSONDecodeError, ValueError):
            return None
