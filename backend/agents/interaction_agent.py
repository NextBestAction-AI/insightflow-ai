"""
backend/agents/interaction_agent.py
=====================================
InteractionAgent — the first business agent of the InsightFlow AI platform.

Single responsibility
---------------------
**Answer one question: "What happened in the customer's interactions?"**

This agent collects every interaction channel present in ``WorkflowState.input``
(transcript, emails, meeting notes, support tickets, CRM notes, chat messages,
call transcripts), normalises and deduplicates the data, submits it to the
LLM via ``LLMService.generate_text``, parses the structured JSON response
into a strongly-typed Pydantic model, and writes the result to
``WorkflowState.analysis.interaction_analysis``.

It is explicitly NOT responsible for:
* Risk analysis
* Customer health scoring
* Recommendations
* Business reasoning
* Knowledge retrieval
* CRM analysis

Reference implementation
------------------------
This module is the **canonical reference** for every future business agent on
the platform.  Study the structure of:

* Declarative ``ClassVar`` metadata for Planner introspection.
* ``execute()`` as a thin orchestrator that delegates to helper components.
* Fully-typed Pydantic output models for safe downstream consumption.
* Component-driven preprocessing via:
  - ``InteractionCollector``: Gathers data from multiple channels in a single place.
  - ``InteractionNormalizer``: Preprocesses raw text and filters short/noisy records.
  - ``InteractionContextBuilder``: Compiles normalized records and customer info into a context dictionary.
  - ``InteractionPromptBuilder``: Connects business prompts with template logic and safety rules.
* Metric recording via ``self._record_llm_call()`` and
  ``self._record_metric()``.
* Graceful error recovery — the agent never raises; all failures become
  ``AgentResult`` with ``success=False``.

Architecture (data flow)
------------------------
::

    execute()
      │
      ├─► InteractionCollector.collect()        — gather all channels from InputState
      │
      ├─► InteractionNormalizer.normalize()     — tag, clean & validate each interaction record
      │
      ├─► _remove_duplicates()                  — deduplicate by (source, content hash)
      │
      ├─► _sort_chronologically()                — deterministic ordering
      │
      ├─► InteractionContextBuilder.build()     — compile structured payload dict
      │
      ├─► InteractionPromptBuilder.build_prompt()— render prompt with groundedness safety rules
      │
      ├─► _call_llm()                           — LLMService.generate_text → PipelineResponse
      │
      ├─► _parse_response()                     — ResponseParser → InteractionAnalysis
      │
      ├─► _validate_analysis()                  — invariant checks; attempt recovery
      │
      └─► _write_state()                        — WorkflowState.analysis.interaction_analysis
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from backend.agents.base_agent import BaseAgent
from backend.orchestrator.agent_result import AgentResult
from backend.orchestrator.execution_context import ExecutionContext
from backend.orchestrator.workflow_state import WorkflowState
from backend.services.llm.exceptions import LLMBaseError, LLMJSONParseError
from backend.services.llm.response_parser import ResponseParser


# =============================================================================
# Section 1: Output schema
# =============================================================================


class ActionItem(BaseModel):
    """
    A single explicit action item extracted from the interaction.

    Attributes
    ----------
    description : str
        What needs to be done.
    owner : str
        Who is responsible (defaults to ``"unassigned"``).
    due_date : str | None
        Free-text due date or deadline as mentioned in the conversation.
    priority : str
        Urgency signal: ``"low"``, ``"medium"``, or ``"high"``.
    """

    description: str = Field(min_length=1, description="What needs to be done.")
    owner: str = Field(default="unassigned", description="Responsible party.")
    due_date: str | None = Field(
        default=None,
        description="Free-text due date or deadline mentioned in the conversation.",
    )
    priority: str = Field(
        default="medium",
        description="Urgency signal: 'low', 'medium', or 'high'.",
    )

    @field_validator("priority", mode="before")
    @classmethod
    def _normalise_priority(cls, v: Any) -> str:
        """Accept any case; coerce to lowercase; default to 'medium' if unknown."""
        normalised = str(v).lower().strip()
        return normalised if normalised in {"low", "medium", "high"} else "medium"


class ExtractedEntity(BaseModel):
    """
    A named entity extracted from the interaction corpus.

    Examples: product names, feature mentions, competitor names, dates,
    monetary amounts, internal project names.

    Attributes
    ----------
    name : str
        Surface form of the entity as it appeared in the text.
    entity_type : str
        Coarse category: ``"product"``, ``"person"``, ``"organisation"``,
        ``"date"``, ``"amount"``, ``"feature"``, ``"competitor"``, or
        ``"other"``.
    context : str | None
        Optional surrounding sentence for disambiguation.
    """

    name: str = Field(min_length=1, description="Surface form of the entity.")
    entity_type: str = Field(description="Coarse entity category.")
    context: str | None = Field(
        default=None,
        description="Surrounding sentence for disambiguation.",
    )


class IssueRecord(BaseModel):
    """
    A problem, complaint, or pain point raised during the interaction.

    Attributes
    ----------
    description : str
        What the issue is, in the customer's own words or paraphrased.
    severity : str
        ``"low"``, ``"medium"``, ``"high"``, or ``"critical"``.
    category : str
        Broad category: ``"technical"``, ``"billing"``, ``"support"``,
        ``"feature_request"``, ``"onboarding"``, ``"performance"``,
        ``"security"``, or ``"other"``.
    status : str
        Current status: ``"open"``, ``"in_progress"``, ``"resolved"``, or
        ``"escalated"``.
    """

    description: str = Field(min_length=1, description="Issue description.")
    severity: str = Field(
        default="medium",
        description="Severity: 'low', 'medium', 'high', or 'critical'.",
    )
    category: str = Field(default="other", description="Broad issue category.")
    status: str = Field(default="open", description="Resolution status.")

    @field_validator("severity", mode="before")
    @classmethod
    def _normalise_severity(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        return normalised if normalised in {"low", "medium", "high", "critical"} else "medium"

    @field_validator("status", mode="before")
    @classmethod
    def _normalise_status(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        return normalised if normalised in {"open", "in_progress", "resolved", "escalated"} else "open"


class CommitmentRecord(BaseModel):
    """
    A promise or commitment made by either party during the interaction.

    Attributes
    ----------
    description : str
        What was committed to.
    made_by : str
        Who made the commitment (``"customer"``, ``"sales_rep"``,
        ``"support_engineer"``, or a named individual).
    due_date : str | None
        When the commitment is due, as mentioned in the conversation.
    """

    description: str = Field(min_length=1, description="What was committed.")
    made_by: str = Field(default="unknown", description="Who made the commitment.")
    due_date: str | None = Field(
        default=None, description="Commitment deadline as mentioned."
    )


class InteractionAnalysis(BaseModel):
    """
    Strongly-typed output model for the InteractionAgent.

    This is the canonical shape of ``WorkflowState.analysis.interaction_analysis``
    after the ``InteractionAgent`` has run.  Downstream agents (``RiskAgent``,
    ``HealthAgent``, ``ReasoningAgent``) read from this model — never from
    the raw LLM text.

    Attributes
    ----------
    sentiment : str
        Overall sentiment: ``"positive"``, ``"neutral"``, ``"negative"``,
        or ``"mixed"``.
    urgency : str
        Urgency level: ``"low"``, ``"medium"``, ``"high"``, or ``"critical"``.
    issues : list[IssueRecord]
        Structured problem/complaint records.
    entities : list[ExtractedEntity]
        Named entities extracted from the corpus.
    action_items : list[ActionItem]
        Explicit action items with ownership and due dates.
    summary : str
        Concise narrative summary of what happened in the interaction.
    confidence : float | None
        Self-reported model confidence in [0.0, 1.0]; ``None`` if absent.
    """

    # ── Sentiment & Urgency ────────────────────────────────────────────────
    sentiment: str = Field(
        default="neutral",
        description="Overall sentiment: 'positive', 'neutral', 'negative', or 'mixed'.",
    )
    urgency: str = Field(
        default="medium",
        description="Urgency level: 'low', 'medium', 'high', or 'critical'.",
    )

    # ── Extracted intelligence ─────────────────────────────────────────────
    issues: list[IssueRecord] = Field(
        default_factory=list,
        description="Structured problem/complaint records.",
    )
    entities: list[ExtractedEntity] = Field(
        default_factory=list,
        description="Named entities extracted from the corpus.",
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="Explicit action items with ownership and due dates.",
    )

    # ── Narrative ─────────────────────────────────────────────────────────
    summary: str = Field(
        default="",
        description="Concise narrative summary of what happened in the interaction.",
    )

    # ── Provenance ─────────────────────────────────────────────────────────
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Self-reported model confidence in [0.0, 1.0].",
    )

    # ── Validators ─────────────────────────────────────────────────────────

    @field_validator("sentiment", mode="before")
    @classmethod
    def _normalise_sentiment(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        return normalised if normalised in {"positive", "neutral", "negative", "mixed"} else "neutral"

    @field_validator("urgency", mode="before")
    @classmethod
    def _normalise_urgency(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        return normalised if normalised in {"low", "medium", "high", "critical"} else "medium"


# =============================================================================
# Section 2: Normalised interaction record (internal DTO)
# =============================================================================


class _NormalisedInteraction:
    """
    Internal data-transfer object representing a single normalised interaction.

    Not exposed outside this module.  The preprocessor converts raw
    ``InputState`` fields into a list of these records, which are then
    serialised into the LLM prompt context.

    Attributes
    ----------
    source : str
        Origin channel (e.g. ``"transcript"``, ``"email"``, ``"meeting_notes"``).
    content : str
        Cleaned, non-empty body text.
    content_hash : str
        SHA-256 (first 16 hex chars) of the content for deduplication.
    sequence : int
        Original discovery order (used as fallback sort key when no
        timestamp is available).
    """

    __slots__ = ("source", "content", "content_hash", "sequence")

    def __init__(self, source: str, content: str, sequence: int) -> None:
        self.source: str = source
        self.content: str = content.strip()
        self.content_hash: str = hashlib.sha256(
            self.content.encode("utf-8", errors="replace")
        ).hexdigest()[:16]
        self.sequence: int = sequence

    def to_dict(self) -> dict[str, str | int]:
        """Serialise to a JSON-safe dict for prompt construction."""
        return {
            "source": self.source,
            "content": self.content,
        }

    def __repr__(self) -> str:
        return (
            f"_NormalisedInteraction("
            f"source={self.source!r} "
            f"chars={len(self.content)} "
            f"hash={self.content_hash!r})"
        )


# =============================================================================
# Section 3: Private Helper Components for Interaction Processing
# =============================================================================


class InteractionCollector:
    """
    Collector component responsible for gathering raw interaction data from WorkflowState.

    WHY THIS HELPER EXISTS:
    To cleanly separate data retrieval from execution orchestration. This allows
    us to adapt or mock the data sources (e.g. adding new input channels) without
    modifying the primary execution flow of the agent.
    """

    def collect(self, state: WorkflowState) -> list[dict[str, str]]:
        """
        Gather all available interaction records from ``WorkflowState``.

        Scans all supported channel sources in priority order:
        1. ``state.input.transcript``           — primary call / meeting transcript
        2. ``state.input.emails``               — email bodies (one per entry)
        3. ``state.input.meeting_notes``        — unstructured meeting notes
        4. ``state.input.user_query``           — direct user query / message
        5. ``state.context.historical_interactions`` — previous interaction records
        6. ``state.context.crm_context``        — CRM notes (if non-empty dict)

        Parameters
        ----------
        state : WorkflowState
            Current workflow state.

        Returns
        -------
        list[dict[str, str]]
            Raw records: ``{"source": str, "content": str}``.
        """
        records: list[dict[str, str]] = []

        # Channel 1: main call / meeting transcript
        if state.input.transcript:
            records.append({
                "source": "transcript",
                "content": state.input.transcript,
            })

        # Channel 2: email bodies (one record per email)
        for idx, email_body in enumerate(state.input.emails):
            if email_body:
                records.append({
                    "source": f"email_{idx + 1}",
                    "content": email_body,
                })

        # Channel 3: meeting notes
        if state.input.meeting_notes:
            records.append({
                "source": "meeting_notes",
                "content": state.input.meeting_notes,
            })

        # Channel 4: user query (treat as direct text input)
        if state.input.user_query:
            records.append({
                "source": "user_query",
                "content": state.input.user_query,
            })

        # Channel 5: historical interaction records from context
        for idx, hist in enumerate(state.context.historical_interactions):
            content = hist.get("content") or hist.get("transcript") or hist.get("notes")
            if content and isinstance(content, str):
                source_label = hist.get("source") or f"historical_{idx + 1}"
                records.append({
                    "source": str(source_label),
                    "content": content,
                })

        # Channel 6: CRM context — extract relevant note fields
        if state.context.crm_context:
            crm_notes = state.context.crm_context.get("notes") or \
                        state.context.crm_context.get("account_notes") or \
                        state.context.crm_context.get("opportunity_notes")
            if crm_notes and isinstance(crm_notes, str):
                records.append({
                    "source": "crm_notes",
                    "content": crm_notes,
                })

        return records


class InteractionNormalizer:
    """
    Normalizer component responsible for text cleaning, character length filtering,
    and transforming raw dict payloads into strongly-typed internal DTOs.

    WHY THIS HELPER EXISTS:
    To isolate text preprocessing, formatting, and validation constraints. Doing so
    ensures raw input data is cleaned deterministically before processing by any
    cognitive/LLM layers.
    """

    def __init__(self, min_content_chars: int = 10) -> None:
        self._min_content_chars = min_content_chars
        import re
        self._multi_blank_re = re.compile(r"\n{3,}")

    def normalize(self, raw_records: list[dict[str, str]]) -> list[_NormalisedInteraction]:
        """
        Convert raw interaction dicts into :class:`_NormalisedInteraction` DTOs.

        Normalisation steps performed on each record:
        * Strip leading and trailing whitespace.
        * Collapse runs of more than two consecutive blank lines to two.
        * Skip records whose content is below minimum character threshold.
        * Assign a monotonically increasing ``sequence`` number.

        Parameters
        ----------
        raw_records : list[dict[str, str]]
            Output of InteractionCollector.collect().

        Returns
        -------
        list[_NormalisedInteraction]
            Filtered, cleaned interaction records.
        """
        normalised: list[_NormalisedInteraction] = []
        sequence = 0

        for record in raw_records:
            source = record.get("source", "unknown")
            content = record.get("content", "")

            # Collapse excessive blank lines
            content = self._multi_blank_re.sub("\n\n", content).strip()

            if len(content) < self._min_content_chars:
                continue

            normalised.append(_NormalisedInteraction(source, content, sequence))
            sequence += 1

        return normalised


class InteractionContextBuilder:
    """
    Context builder component responsible for generating the structured payload for
    the LLM prompt context, including customer metadata, corpus summaries, and statistics.

    WHY THIS HELPER EXISTS:
    To encapsulate prompt context compilation. It transforms normalized DTOs and customer
    state into a structured dictionary of prompt-ready variables and computes key statistics
    like total character count.
    """

    def build(
        self,
        state: WorkflowState,
        interactions: list[_NormalisedInteraction],
    ) -> dict[str, Any]:
        """
        Build the structured context payload that feeds the prompt template.

        Assembles:
        * Customer metadata from ``state.customer``.
        * A formatted text block from the interaction corpus.
        * Aggregate statistics (total characters, source list).

        Parameters
        ----------
        state : WorkflowState
            Current workflow state (reads ``state.customer``).
        interactions : list[_NormalisedInteraction]
            Sorted, deduplicated interaction records.

        Returns
        -------
        dict[str, Any]
            Template-ready context payload.
        """
        # Build the interaction text block for the prompt
        interaction_blocks: list[str] = []
        for idx, record in enumerate(interactions, start=1):
            header = f"[{idx}] Source: {record.source}"
            block = f"{header}\n{'-' * len(header)}\n{record.content}"
            interaction_blocks.append(block)

        interactions_text = "\n\n".join(interaction_blocks) if interaction_blocks else "(no interactions)"
        total_chars = sum(len(r.content) for r in interactions)
        sources = list(dict.fromkeys(r.source.split("_")[0] for r in interactions))

        return {
            "customer_name": state.customer.customer_name or "Unknown Customer",
            "company": state.customer.company or "Unknown Company",
            "industry": state.customer.industry or "Unknown Industry",
            "account_type": state.customer.account_type or "Unknown",
            "region": state.customer.region or "Unknown",
            "interaction_count": len(interactions),
            "sources_list": ", ".join(sources) if sources else "unknown",
            "interactions_text": interactions_text,
            "total_chars": total_chars,
            "sources": sources,
        }


class InteractionPromptBuilder:
    """
    Prompt builder component responsible for taking structured context and orchestrating
    rendering via the generic PromptManager.

    WHY THIS HELPER EXISTS:
    To shield the core agent from template-specific variables and formatting details.
    The generic PromptManager does not know about business context; the PromptBuilder
    acts as the business-aware translation layer that configures template parameters.
    """

    def __init__(self, prompt_manager: Any, prompt_template: str) -> None:
        self._prompt_manager = prompt_manager
        self._prompt_template = prompt_template

    def build_prompt(self, context_payload: dict[str, Any]) -> str:
        """
        Construct the LLM prompt by rendering the template with variables.

        Parameters
        ----------
        context_payload : dict[str, Any]
            The structured context payload containing customer details and interaction text.

        Returns
        -------
        str
            Fully-rendered prompt string, ready to send to the LLM.
        """
        return self._prompt_manager.render_string(
            self._prompt_template,
            customer_name=context_payload["customer_name"],
            company=context_payload["company"],
            industry=context_payload["industry"],
            account_type=context_payload["account_type"],
            region=context_payload["region"],
            interaction_count=context_payload["interaction_count"],
            sources_list=context_payload["sources_list"],
            interactions_text=context_payload["interactions_text"],
        )


# ---------------------------------------------------------------------------
# Prompt template — defined as a module constant. Uses str.format_map placeholders.
# ---------------------------------------------------------------------------
_INTERACTION_ANALYSIS_PROMPT: str = """\
You are an expert Customer Success Intelligence analyst embedded in an \
enterprise Agentic AI platform.

Your task is to analyse the customer interactions provided below and \
return a structured intelligence report in **strict JSON** format.

## Customer Context
- Customer: {customer_name}
- Company: {company}
- Industry: {industry}
- Account Type: {account_type}
- Region: {region}

## Interaction Corpus
The following {interaction_count} interaction record(s) were collected \
from {sources_list}:

{interactions_text}

## Required Output
Return ONLY a single, valid JSON object with exactly the following fields. \
Do not add any prose, markdown fences, or explanation outside the JSON object.

{{
  "sentiment": "<positive | neutral | negative | mixed>",
  "urgency": "<low | medium | high | critical>",
  "issues": [
    {{
      "description": "<issue description>",
      "severity": "<low | medium | high | critical>",
      "category": "<technical | billing | support | feature_request | \
onboarding | performance | security | other>",
      "status": "<open | in_progress | resolved | escalated>"
    }}
  ],
  "entities": [
    {{
      "name": "<entity surface form>",
      "entity_type": "<product | person | organisation | date | amount | \
feature | competitor | other>",
      "context": "<surrounding sentence or null>"
    }}
  ],
  "action_items": [
    {{
      "description": "<what needs to be done>",
      "owner": "<responsible party or 'unassigned'>",
      "due_date": "<free-text date string or null>",
      "priority": "<low | medium | high>"
    }}
  ],
  "summary": "<concise 3–5 sentence narrative of what happened>",
  "confidence": <float in [0.0, 1.0]>
}}

## Prompt Safety & Groundedness Rules:
1. NEVER invent information. Do not hallucinate or assume facts.
2. NEVER infer unsupported facts. Every extracted detail must be directly grounded in the provided interaction text.
3. Every issue must be directly supported by the interaction text.
4. Every action item must originate from the interaction.
5. Unknown information must be returned as null or an empty list (e.g. if due_date is unknown, use null; if issues/action_items are empty, use []).
6. Keep entity names exactly as they appear in the text; do not normalise.
7. Output STRICT JSON only. Do not include markdown code blocks (e.g. ```json ... ```) or any surrounding conversational filler text.
"""

_SYSTEM_PROMPT: str = (
    "You are a structured JSON extraction engine. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)


# =============================================================================
# Section 4: The Agent
# =============================================================================


class InteractionAgent(BaseAgent):
    """
    Analyses customer interactions and extracts structured interaction intelligence.

    This is the canonical first business agent of the InsightFlow AI platform
    and the reference implementation for all future domain agents.

    Responsibility
    --------------
    Answer **"What happened in the customer's interactions?"** by:

    1. Collecting every available interaction channel from ``WorkflowState.input``:
       call transcripts, emails, meeting notes, historical interaction records
       (from ``state.context``), CRM notes (from ``state.context.crm_context``),
       and any raw ``user_query`` text.
    2. Normalising, deduplicating, and sorting the corpus deterministically.
    3. Building a structured prompt via ``PromptManager.render_string``.
    4. Calling ``LLMService.generate_text`` to obtain the structured analysis.
    5. Parsing the raw LLM output into an :class:`InteractionAnalysis` model.
    6. Writing the validated result to
       ``WorkflowState.analysis.interaction_analysis``.
    7. Also promoting ``sentiment_score``, ``key_topics``, and
       ``action_items`` to the corresponding top-level ``AnalysisState``
       fields for convenience of downstream agents.

    Planner metadata
    ----------------
    The Planner reads :meth:`~backend.agents.base_agent.BaseAgent.get_agent_metadata`
    to schedule this agent.  It declares:

    * ``required_inputs`` — the agent is schedulable as long as at least
      one of ``input.transcript``, ``input.emails``, ``input.meeting_notes``,
      or ``context.historical_interactions`` is present.  The agent itself
      handles gracefully the case where not all sources are present.
    * ``produced_outputs`` — guarantees that
      ``analysis.interaction_analysis`` will be written on success.

    Parameters
    ----------
    llm_service : LLMService | None
        Injected ``LLMService``; defaults to ``create_llm_service()``.
    prompt_manager : PromptManager | None
        Injected ``PromptManager``; defaults to ``PromptManager()``.
    state_validator : StateValidator | None
        Injected ``StateValidator``; defaults to ``StateValidator()``.
    response_parser : ResponseParser | None
        Injected ``ResponseParser``; defaults to ``ResponseParser()``.
    collector : InteractionCollector | None
        Injected ``InteractionCollector`` for modular data gathering.
    normalizer : InteractionNormalizer | None
        Injected ``InteractionNormalizer`` for preprocessing raw messages.
    context_builder : InteractionContextBuilder | None
        Injected ``InteractionContextBuilder`` for generating template variables.
    prompt_builder : InteractionPromptBuilder | None
        Injected ``InteractionPromptBuilder`` for prompt formatting and safety injection.
    """

    # ── Planner metadata ─────────────────────────────────────────────────────

    agent_name: ClassVar[str] = "InteractionAgent"

    description: ClassVar[str] = (
        "Analyses customer interactions from all available channels and extracts "
        "structured intelligence: sentiment, issues, entities, action items, "
        "commitments, and a narrative summary."
    )

    required_inputs: ClassVar[list[str]] = [
        # At least one of these must be present; the agent handles missing ones.
        "input.transcript",
        "input.emails",
        "input.meeting_notes",
        "context.historical_interactions",
    ]

    produced_outputs: ClassVar[list[str]] = [
        "analysis.interaction_analysis",
    ]

    supported_execution_modes: ClassVar[list[str]] = [
        "LIVE",
        "DEBUG",
        "DRY_RUN",
        "SIMULATION",
    ]

    priority: ClassVar[int] = 100
    """
    Scheduled first in the default pipeline because all other analytical
    agents depend on the interaction analysis to reason about customer state.
    """

    # ── Minimum interaction content threshold ─────────────────────────────────
    _MIN_CONTENT_CHARS: ClassVar[int] = 10
    """
    Minimum number of characters a raw interaction string must contain to
    be admitted to the analysis corpus.  Single-word or near-empty strings
    are excluded as noise.
    """

    # ── LLM configuration ─────────────────────────────────────────────────────
    _LLM_TEMPERATURE: ClassVar[float] = 0.1
    """
    Low temperature for structured extraction — we want deterministic,
    factual output rather than creative generation.
    """
    _LLM_MAX_TOKENS: ClassVar[int] = 4096
    """
    Maximum output tokens.  Interaction corpora can be large; cap at 4 096
    to stay within provider limits while leaving enough room for a complete
    JSON payload.
    """

    # =========================================================================
    # Constructor
    # =========================================================================

    def __init__(
        self,
        llm_service=None,
        prompt_manager=None,
        state_validator=None,
        response_parser: ResponseParser | None = None,
        collector: InteractionCollector | None = None,
        normalizer: InteractionNormalizer | None = None,
        context_builder: InteractionContextBuilder | None = None,
        prompt_builder: InteractionPromptBuilder | None = None,
    ) -> None:
        super().__init__(
            llm_service=llm_service,
            prompt_manager=prompt_manager,
            state_validator=state_validator,
        )
        self._parser: ResponseParser = response_parser or ResponseParser()
        self._collector: InteractionCollector = collector or InteractionCollector()
        self._normalizer: InteractionNormalizer = normalizer or InteractionNormalizer(
            min_content_chars=self._MIN_CONTENT_CHARS
        )
        self._context_builder: InteractionContextBuilder = context_builder or InteractionContextBuilder()
        self._prompt_builder: InteractionPromptBuilder = prompt_builder or InteractionPromptBuilder(
            prompt_manager=self.prompts,
            prompt_template=_INTERACTION_ANALYSIS_PROMPT,
        )

    # =========================================================================
    # Lifecycle hooks
    # =========================================================================

    async def validate_input(
        self,
        state: WorkflowState,
        context: ExecutionContext,
    ) -> None:
        """
        Verify that the workflow state contains at least one interaction channel.

        WHY THIS HOOK EXISTS
        ~~~~~~~~~~~~~~~~~~~~
        Catching missing data early (before the LLM call) produces a clean,
        actionable failure message rather than a cryptic empty-prompt error.

        Raises
        ------
        ValueError
            If absolutely no interaction content is available anywhere in
            the state.  The base-class ``run()`` catches this and converts
            it to a failure ``AgentResult``.
        """
        has_input = any([
            bool(state.input.transcript),
            bool(state.input.emails),
            bool(state.input.meeting_notes),
            bool(state.context.historical_interactions),
            bool(state.context.crm_context),
            bool(state.input.user_query),
        ])
        if not has_input:
            raise ValueError(
                "InteractionAgent requires at least one interaction channel "
                "(transcript, emails, meeting_notes, historical_interactions, "
                "crm_context, or user_query) but all are empty or absent."
            )
        self._logger.debug(
            "[InteractionAgent] Input validation passed — has_input=%s", has_input
        )

    # =========================================================================
    # Core business logic
    # =========================================================================

    async def execute(
        self,
        state: WorkflowState,
        context: ExecutionContext,
    ) -> AgentResult:
        """
        Orchestrate the full interaction analysis pipeline.

        This method is intentionally thin — it delegates every step to its
        private helpers and modular components.

        Parameters
        ----------
        state:
            Shared workflow state.  Reads from ``state.input`` and
            ``state.context``; writes to ``state.analysis``.
        context:
            Immutable runtime context carrying correlation IDs and mode.

        Returns
        -------
        AgentResult
            Success result carrying the serialised :class:`InteractionAnalysis`
            as ``output_data``; or a failure result with structured error
            descriptions.  ``execution_time_ms`` is overwritten by
            :meth:`~backend.agents.base_agent.BaseAgent.run`.
        """
        self._logger.info(
            "[InteractionAgent] Starting interaction analysis | request_id=%s",
            context.request_id,
        )

        # ── Step 1: Collect raw interactions (delegated to InteractionCollector) ──
        raw_interactions = self._collect_interactions(state)
        self._logger.info(
            "[InteractionAgent] Collected %d raw interaction record(s).",
            len(raw_interactions),
        )

        # ── Step 2: Normalise (delegated to InteractionNormalizer) ─────────────
        normalised = self._normalise_interactions(raw_interactions)
        self._logger.info(
            "[InteractionAgent] Normalisation complete — %d record(s) after filtering.",
            len(normalised),
        )
        self._record_metric("raw_interaction_count", len(raw_interactions))
        self._record_metric("normalised_interaction_count", len(normalised))

        # ── Step 3: Deduplicate ───────────────────────────────────────────────
        unique = self._remove_duplicates(normalised)
        if len(unique) < len(normalised):
            duplicates_removed = len(normalised) - len(unique)
            self._add_warning(
                f"Removed {duplicates_removed} duplicate interaction record(s)."
            )
            self._record_metric("duplicates_removed", duplicates_removed)
        self._logger.debug(
            "[InteractionAgent] %d unique record(s) after deduplication.", len(unique)
        )

        # ── Step 4: Sort chronologically ─────────────────────────────────────
        ordered = self._sort_chronologically(unique)

        # ── Step 5: Prepare context payload (delegated to InteractionContextBuilder) ──
        context_payload = self._prepare_context(state, ordered)
        total_chars = context_payload["total_chars"]
        self._record_metric("chars_processed", total_chars)
        self._logger.debug(
            "[InteractionAgent] Context prepared — %d char(s) across %d source(s).",
            total_chars,
            len(context_payload["sources"]),
        )

        # ── Step 6: Build prompt (delegated to InteractionPromptBuilder) ──────
        prompt = self._build_prompt(state, context_payload)
        self._logger.info(
            "[InteractionAgent] Prompt generated — length=%d char(s).", len(prompt)
        )

        # ── Step 7: Call the LLM ──────────────────────────────────────────────
        self._logger.info("[InteractionAgent] Invoking LLM for interaction analysis.")
        llm_start = time.monotonic()
        pipeline_response = await self._call_llm(prompt)
        llm_latency_ms = (time.monotonic() - llm_start) * 1_000.0
        self._record_llm_call()
        self._record_metric("llm_latency_ms", round(llm_latency_ms, 2))
        self._record_metric("prompt_tokens", pipeline_response.prompt_tokens)
        self._record_metric("output_tokens", pipeline_response.output_tokens)
        self._logger.info(
            "[InteractionAgent] LLM completed | latency_ms=%.1f tokens=%d+%d.",
            llm_latency_ms,
            pipeline_response.prompt_tokens,
            pipeline_response.output_tokens,
        )

        # ── Step 8: Parse LLM response ────────────────────────────────────────
        analysis = self._parse_response(pipeline_response.text, ordered)
        self._logger.info("[InteractionAgent] Response parsed successfully.")
        self._record_metric("issues_extracted", len(analysis.issues))
        self._record_metric("entities_extracted", len(analysis.entities))
        self._record_metric("action_items_extracted", len(analysis.action_items))

        # ── Step 9: Validate ──────────────────────────────────────────────────
        analysis = self._validate_analysis(analysis, ordered)
        self._logger.info("[InteractionAgent] Validation successful.")

        # ── Step 10: Write state ──────────────────────────────────────────────
        self._write_state(state, analysis)
        self._logger.info(
            "[InteractionAgent] WorkflowState updated — "
            "interaction_analysis written."
        )

        # ── Step 11: Build success AgentResult ───────────────────────────────
        output_data = analysis.model_dump(mode="json")

        self._logger.info(
            "[InteractionAgent] Analysis complete | sentiment=%s urgency=%s "
            "issues=%d action_items=%d entities=%d",
            analysis.sentiment,
            analysis.urgency,
            len(analysis.issues),
            len(analysis.action_items),
            len(analysis.entities),
        )

        return AgentResult.success_result(
            agent_name=self.agent_name,
            execution_time_ms=0.0,  # overwritten by BaseAgent.run()
            output_data=output_data,
            confidence=analysis.confidence,
            message=(
                f"Successfully analysed {analysis.interaction_count} "
                f"interaction(s) — sentiment={analysis.sentiment}, "
                f"urgency={analysis.urgency}, "
                f"issues={len(analysis.issues)}, "
                f"action_items={len(analysis.action_items)}."
            ),
        )

    # =========================================================================
    # Error handling override
    # =========================================================================

    async def handle_error(
        self,
        exc: Exception,
        state: WorkflowState,
        context: ExecutionContext,
    ) -> AgentResult | None:
        """
        Attempt lightweight recovery before producing a failure result.

        Recovery strategy
        ~~~~~~~~~~~~~~~~~
        * ``LLMJSONParseError`` — the LLM returned invalid JSON.  We attempt
          to write a minimal stub analysis to state so downstream agents
          can continue with reduced information, and return a failure result
          to inform the workflow engine that the data is incomplete.
        * All other failures — return ``None`` to let ``BaseAgent`` build
          the default failure result.

        Parameters
        ----------
        exc:
            The exception that triggered the error path.
        state:
            Current workflow state (may be partially mutated).
        context:
            Immutable runtime context.

        Returns
        -------
        AgentResult | None
            A failure result for ``LLMJSONParseError``; ``None`` for all
            other exception types (delegating to the default handler).
        """
        if isinstance(exc, LLMJSONParseError):
            self._logger.warning(
                "[InteractionAgent] JSON parse failure — will record minimal stub "
                "analysis and return failure result. request_id=%s",
                context.request_id,
            )
            # Write a stub so state is not left empty, enabling partial workflows.
            stub = InteractionAnalysis(
                summary="[InteractionAgent failed to parse LLM response — partial data only]",
            )
            try:
                self._write_state(state, stub)
            except Exception as write_exc:  # noqa: BLE001
                self._logger.error(
                    "[InteractionAgent] Stub write also failed: %s", write_exc
                )

            return AgentResult.failure_result(
                agent_name=self.agent_name,
                execution_time_ms=0.0,  # overwritten by BaseAgent
                errors=[
                    f"LLMJSONParseError: {exc}",
                    "Interaction analysis could not be completed. "
                    "A stub analysis has been written to state.",
                ],
                message="LLM returned malformed JSON; recovery stub written to state.",
            )

        # Delegate all other failures to BaseAgent's default handler.
        return None

    # =========================================================================
    # Private preprocessing helpers (delegating to helper components)
    # =========================================================================

    def _collect_interactions(
        self,
        state: WorkflowState,
    ) -> list[dict[str, str]]:
        """
        Gather all available interaction records from ``WorkflowState``.

        Delegated to ``InteractionCollector``.
        """
        return self._collector.collect(state)

    def _normalise_interactions(
        self,
        raw_records: list[dict[str, str]],
    ) -> list[_NormalisedInteraction]:
        """
        Convert raw interaction dicts into :class:`_NormalisedInteraction` DTOs.

        Delegated to ``InteractionNormalizer``.
        """
        return self._normalizer.normalize(raw_records)

    def _remove_duplicates(
        self,
        interactions: list[_NormalisedInteraction],
    ) -> list[_NormalisedInteraction]:
        """
        Remove duplicate interaction records.

        Two records are considered duplicates when their ``content_hash``
        values are identical.  The first occurrence (lowest ``sequence``
        number) is kept; subsequent duplicates are discarded.

        Preserves the original ordering of the first occurrences.
        """
        seen_hashes: set[str] = set()
        unique: list[_NormalisedInteraction] = []

        for record in interactions:
            if record.content_hash not in seen_hashes:
                seen_hashes.add(record.content_hash)
                unique.append(record)
            else:
                self._logger.debug(
                    "[InteractionAgent] Duplicate removed — source=%r hash=%s",
                    record.source,
                    record.content_hash,
                )

        return unique

    def _sort_chronologically(
        self,
        interactions: list[_NormalisedInteraction],
    ) -> list[_NormalisedInteraction]:
        """
        Sort interaction records into a stable, chronological order.

        1. Apply a deterministic source-type priority:
           ``transcript`` > ``meeting_notes`` > ``email_*`` >
           ``crm_notes`` > ``user_query`` > ``historical_*`` > all others.
        2. Within the same source-type priority, preserve the original
           ``sequence`` number.
        """
        SOURCE_PRIORITY: dict[str, int] = {
            "transcript": 0,
            "meeting_notes": 1,
            "crm_notes": 3,
            "user_query": 4,
        }
        DEFAULT_PRIORITY = 5  # email_*, historical_*, unknown, etc.

        def _sort_key(record: _NormalisedInteraction) -> tuple[int, int]:
            base = record.source.split("_")[0]
            priority = SOURCE_PRIORITY.get(record.source) or \
                       SOURCE_PRIORITY.get(base, DEFAULT_PRIORITY)
            return (priority, record.sequence)

        return sorted(interactions, key=_sort_key)

    def _prepare_context(
        self,
        state: WorkflowState,
        interactions: list[_NormalisedInteraction],
    ) -> dict[str, Any]:
        """
        Build the structured context payload that feeds the prompt template.

        Delegated to ``InteractionContextBuilder``.
        """
        return self._context_builder.build(state, interactions)

    def _build_prompt(
        self,
        state: WorkflowState,
        context_payload: dict[str, Any],
    ) -> str:
        """
        Construct the LLM prompt by rendering the template with variables.

        Delegated to ``InteractionPromptBuilder``.
        """
        return self._prompt_builder.build_prompt(context_payload)

    async def _call_llm(self, prompt: str):
        """
        Submit the rendered prompt to the LLM via ``LLMService.generate_text``.
        """
        return await self.llm.generate_text(
            raw_prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=self._LLM_TEMPERATURE,
            max_tokens=self._LLM_MAX_TOKENS,
            cache_enabled=True,
        )

    def _parse_response(
        self,
        raw_text: str,
        interactions: list[_NormalisedInteraction],
    ) -> InteractionAnalysis:
        """
        Parse the raw LLM output text into a validated :class:`InteractionAnalysis`.

        Uses the injected :class:`ResponseParser` to extract and validate JSON.
        """
        self._logger.debug(
            "[InteractionAgent] Parsing LLM response — raw_len=%d", len(raw_text)
        )
        analysis = self._parser.parse_json_as(raw_text, InteractionAnalysis)

        self._logger.debug(
            "[InteractionAgent] Parsing complete — sentiment=%s urgency=%s",
            analysis.sentiment,
            analysis.urgency,
        )
        return analysis

    def _validate_analysis(
        self,
        analysis: InteractionAnalysis,
        interactions: list[_NormalisedInteraction],
    ) -> InteractionAnalysis:
        """
        Apply post-parse invariant checks and lightweight recovery.
        """
        updates: dict[str, Any] = {}

        # Invariant 1: summary must be non-empty
        if not analysis.summary.strip():
            fallback_summary = (
                f"Interaction analysis of {len(interactions)} record(s) "
                f"from source(s): {', '.join(r.source for r in interactions)}. "
                f"Sentiment: {analysis.sentiment}. Urgency: {analysis.urgency}."
            )
            updates["summary"] = fallback_summary
            self._add_warning(
                "LLM returned an empty summary — a fallback summary was synthesised."
            )
            self._logger.warning(
                "[InteractionAgent] Empty summary from LLM — fallback applied."
            )

        if updates:
            analysis = analysis.model_copy(update=updates)

        return analysis

    def _write_state(
        self,
        state: WorkflowState,
        analysis: InteractionAnalysis,
    ) -> None:
        """
        Write the validated :class:`InteractionAnalysis` to ``WorkflowState``.
        """
        full_payload = analysis.model_dump(mode="json")
        state.analysis.interaction_analysis = full_payload

        self._logger.debug(
            "[InteractionAgent] State written — interaction_analysis size=%d keys.",
            len(full_payload),
        )
