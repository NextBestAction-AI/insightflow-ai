"""
backend/services/llm/prompt_manager.py
========================================
Prompt template management — load, render, and return final prompts.

Design
------
* Templates are stored as plain ``.txt`` or ``.jinja2`` files under the
  ``prompts/`` directory (configurable via ``PROMPTS_DIR``).
* Placeholders follow Jinja2 syntax: ``{{ variable_name }}``.
* No prompts are hard-coded here; this class is purely infrastructure.
* Caches loaded templates in memory to avoid repeated disk reads.

Usage
-----
    manager = PromptManager()
    prompt = manager.render("customer_health", customer_name="Acme Corp", score=72)
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from string import Template
from typing import Any

logger = logging.getLogger(__name__)

# Default location for prompt template files, relative to the project root.
_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


class PromptManager:
    """
    Loads prompt templates from the filesystem and renders them with
    caller-supplied variables.

    Supports two rendering strategies (auto-detected from file extension):

    ``*.txt``
        Python ``str.format_map`` placeholders — ``{variable_name}``.
    ``*.jinja2`` / ``*.j2``
        Jinja2 template syntax — ``{{ variable_name }}``.
        Requires the optional ``jinja2`` package to be installed.

    Parameters
    ----------
    prompts_dir:
        Directory that contains ``.txt`` / ``.jinja2`` template files.
        Reads ``PROMPTS_DIR`` env var first; falls back to ``_DEFAULT_PROMPTS_DIR``.
    """

    def __init__(self, prompts_dir: Path | str | None = None) -> None:
        env_dir = os.getenv("PROMPTS_DIR")
        self._prompts_dir: Path = (
            Path(prompts_dir)
            if prompts_dir
            else (Path(env_dir) if env_dir else _DEFAULT_PROMPTS_DIR)
        )
        self._cache: dict[str, str] = {}   # template_name → raw template string
        logger.info("PromptManager initialised — dir=%s", self._prompts_dir)

    # ── Public API ──────────────────────────────────────────────────────────

    def render(self, template_name: str, **variables: Any) -> str:
        """
        Load (or retrieve from cache) a template and render it.

        Parameters
        ----------
        template_name:
            Filename without extension (e.g. ``"customer_health"``).
            Both ``customer_health.txt`` and ``customer_health.jinja2`` are
            searched in order.
        **variables:
            Key-value pairs used to fill template placeholders.

        Returns
        -------
        str
            The fully-rendered prompt string, ready to send to a client.

        Raises
        ------
        FileNotFoundError
            If no matching template file is found.
        KeyError
            If a required placeholder is missing from ``variables``.
        """
        raw_template, extension = self._load_template(template_name)
        rendered = self._render_template(raw_template, extension, variables)
        logger.debug(
            "Rendered template '%s' — output_len=%d", template_name, len(rendered)
        )
        return rendered

    def render_string(self, template_string: str, **variables: Any) -> str:
        """
        Render an ad-hoc template string without loading from disk.

        Useful for dynamically constructed prompts that do not warrant a
        dedicated template file.

        Parameters
        ----------
        template_string:    Raw template text with ``{variable}`` placeholders.
        **variables:        Substitution values.

        Returns
        -------
        str
            The rendered prompt string.
        """
        try:
            rendered = template_string.format_map(variables)
        except KeyError as exc:
            raise KeyError(
                f"Missing placeholder in template string: {exc}"
            ) from exc
        logger.debug("Rendered inline template — output_len=%d", len(rendered))
        return rendered

    def list_templates(self) -> list[str]:
        """
        Return the names of all available template files (without extensions).

        Returns
        -------
        list[str]
        """
        if not self._prompts_dir.exists():
            logger.warning(
                "Prompts directory does not exist: %s", self._prompts_dir
            )
            return []

        names = [
            p.stem
            for p in self._prompts_dir.iterdir()
            if p.suffix in {".txt", ".jinja2", ".j2"} and p.is_file()
        ]
        logger.debug("Available templates: %s", names)
        return sorted(names)

    def clear_cache(self) -> None:
        """Evict all cached template strings (useful in tests)."""
        self._cache.clear()
        logger.debug("Template cache cleared.")

    # ── Private helpers ─────────────────────────────────────────────────────

    def _load_template(self, template_name: str) -> tuple[str, str]:
        """
        Locate, read, and cache the template file for ``template_name``.

        Returns
        -------
        tuple[str, str]
            A ``(raw_template_string, file_extension)`` pair.

        Raises
        ------
        FileNotFoundError
            If neither a ``.txt`` nor a ``.jinja2``/``.j2`` file is found.
        """
        if template_name in self._cache:
            # Cache key stores extension as suffix after "|"
            cached = self._cache[template_name]
            ext = self._cache.get(f"_ext|{template_name}", ".txt")
            return cached, ext

        search_order = [
            (self._prompts_dir / f"{template_name}.txt", ".txt"),
            (self._prompts_dir / f"{template_name}.jinja2", ".jinja2"),
            (self._prompts_dir / f"{template_name}.j2", ".j2"),
        ]

        for path, ext in search_order:
            if path.exists():
                raw = path.read_text(encoding="utf-8")
                self._cache[template_name] = raw
                self._cache[f"_ext|{template_name}"] = ext
                logger.debug("Loaded template '%s' from %s", template_name, path)
                return raw, ext

        raise FileNotFoundError(
            f"Prompt template '{template_name}' not found in {self._prompts_dir}. "
            f"Searched: {[str(p) for p, _ in search_order]}"
        )

    @staticmethod
    def _render_template(
        raw: str, extension: str, variables: dict[str, Any]
    ) -> str:
        """
        Render ``raw`` using the strategy appropriate for ``extension``.

        ``.txt``                    → ``str.format_map``
        ``.jinja2`` / ``.j2``       → Jinja2 ``Template.render``

        Parameters
        ----------
        raw:        Raw template string.
        extension:  File extension including the leading dot.
        variables:  Substitution mapping.

        Returns
        -------
        str
        """
        if extension == ".txt":
            try:
                return raw.format_map(variables)
            except KeyError as exc:
                raise KeyError(
                    f"Missing placeholder {exc} in template. "
                    f"Provided keys: {list(variables.keys())}"
                ) from exc

        # Jinja2 rendering path
        if extension in {".jinja2", ".j2"}:
            try:
                from jinja2 import Template, UndefinedError  # type: ignore[import]
            except ImportError as exc:
                raise ImportError(
                    "Jinja2 is required for .jinja2 templates. "
                    "Run: pip install jinja2"
                ) from exc
            try:
                return Template(raw).render(**variables)
            except UndefinedError as exc:
                raise KeyError(
                    f"Undefined variable in Jinja2 template: {exc}"
                ) from exc

        # Fallback: return raw (no substitution)
        logger.warning(
            "Unknown template extension '%s'; returning raw template.", extension
        )
        return raw
