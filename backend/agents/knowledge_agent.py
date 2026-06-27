"""
backend/agents/knowledge_agent.py
==================================
KnowledgeAgent — retrieves and synthesizes enterprise knowledge relevant to
customer interactions.

Single responsibility
---------------------
**Answer one question: "What does the organization already know about this customer's situation?"**

This agent retrieves relevant documents (playbooks, product docs, troubleshooting
guides, known limitations, best practices, previous cases) from the enterprise
knowledge base using semantic search queries built from the interaction analysis.
It then uses LLMService to synthesize these documents into a cohesive context
report and writes it to ``WorkflowState.context.knowledge_context``.

It is explicitly NOT responsible for:
* Risk Analysis
* Customer Health Scoring
* CRM Analysis
* Business Reasoning
* Recommendations
* Explanations

Reference RAG implementation
----------------------------
Following the clean architecture patterns of the platform, the agent delegates
responsibilities to helper components:
* ``KnowledgeQueryBuilder``: Generates search queries and expands keywords.
* ``KnowledgeService``: Handles vector database retrieval and ranking.
* ``KnowledgeContextBuilder``: Organizes documents into structured context.
* ``KnowledgePromptBuilder``: Builds business prompts with strict safety rules.
* Output is validated against the ``KnowledgeContext`` Pydantic model.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, ClassVar, List, Dict

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from backend.agents.base_agent import BaseAgent
from backend.orchestrator.agent_result import AgentResult
from backend.orchestrator.execution_context import ExecutionContext
from backend.orchestrator.workflow_state import WorkflowState
from backend.services.llm.exceptions import LLMBaseError, LLMJSONParseError
from backend.services.llm.response_parser import ResponseParser


# =============================================================================
# Section 1: Output schema & Internal Models
# =============================================================================


class RelevantDocument(BaseModel):
    """
    Metadata representation of a document retrieved from the knowledge base.
    """
    doc_id: str = Field(description="Unique document identifier.")
    title: str = Field(description="Document title.")
    type: str = Field(description="Type: playbook, product_doc, troubleshooting_guide, case, limitation, best_practice.")
    score: float = Field(default=0.0, description="Similarity score or relevance ranking score.")


class KnowledgeContext(BaseModel):
    """
    Strongly-typed output model for the KnowledgeAgent.

    This represents the synthesized knowledge state written to
    ``WorkflowState.context.knowledge_context``.
    """
    summary: str = Field(
        default="",
        description="Natural-language synthesis of what is known about this issue and how the organization suggests solving it.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Synthesized confidence value reflecting documentation coverage.",
    )
    relevant_documents: list[RelevantDocument] = Field(
        default_factory=list,
        description="Structured lists of metadata for all documents used.",
    )


class KnowledgeDocument:
    """
    Internal representation of an enterprise document in the repository.
    """
    __slots__ = ("doc_id", "title", "type", "content", "tags")

    def __init__(self, doc_id: str, title: str, doc_type: str, content: str, tags: list[str]) -> None:
        self.doc_id = doc_id
        self.title = title
        self.type = doc_type
        self.content = content
        self.tags = tags


class KnowledgeBundle(BaseModel):
    """
    Container for search results returned by KnowledgeService.
    """
    documents: list[RelevantDocument] = Field(default_factory=list)
    document_contents: dict[str, str] = Field(default_factory=dict)
    average_score: float = Field(default=0.0)
    embedding_latency_ms: float = Field(default=0.0)
    search_latency_ms: float = Field(default=0.0)


# =============================================================================
# Section 2: Helper Components
# =============================================================================


class KnowledgeQueryBuilder:
    """
    Helper component responsible for analyzing interaction intelligence and
    generating semantic query intents.

    WHY THIS HELPER EXISTS:
    By isolating search query building, we can change our keyword expansion, synonym
    rules, or use an LLM-assisted query generator without touching the retrieval
    orchestrator.
    """

    def build_queries(self, interaction_analysis: dict[str, Any]) -> list[str]:
        """
        Extract search keywords and compile query variations from interaction issues.

        Parameters
        ----------
        interaction_analysis : dict[str, Any]
            The input interaction analysis model dictionary.

        Returns
        -------
        list[str]
            A list of search query strings.
        """
        queries: list[str] = []

        # 1. Pull topics
        topics = interaction_analysis.get("key_topics", [])
        for topic in topics:
            if isinstance(topic, str) and topic.strip():
                queries.append(topic.strip())

        # 2. Pull entities
        entities = interaction_analysis.get("entities", [])
        for ent in entities:
            if isinstance(ent, dict):
                name = ent.get("name")
                if name and isinstance(name, str):
                    queries.append(name.strip())
            elif isinstance(ent, str):
                queries.append(ent.strip())

        # 3. Pull issue descriptions
        issues = interaction_analysis.get("issues", [])
        for issue in issues:
            desc = ""
            if isinstance(issue, dict):
                desc = issue.get("description", "")
            elif isinstance(issue, str):
                desc = issue

            if desc:
                # Add raw issue
                queries.append(desc)
                # Expand keywords based on simple mappings
                desc_lower = desc.lower()
                if "slow" in desc_lower or "latency" in desc_lower or "performance" in desc_lower:
                    queries.extend(["performance latency", "timeout slow optimization"])
                if "billing" in desc_lower or "invoice" in desc_lower or "charge" in desc_lower:
                    queries.extend(["billing dispute invoice", "charge calculation pricing"])
                if "reporting" in desc_lower or "dashboard" in desc_lower or "analytics" in desc_lower:
                    queries.extend(["reporting latency dashboard", "analytics report performance"])
                if "login" in desc_lower or "auth" in desc_lower or "password" in desc_lower:
                    queries.extend(["authentication credentials login", "session timeout security"])

        # Deduplicate while preserving order
        unique_queries = list(dict.fromkeys(q.strip() for q in queries if q.strip()))
        return unique_queries[:5]  # Limit to top 5 query paths for efficiency


class KnowledgeService:
    """
    RAG service responsible for document retrieval and scoring.

    WHY THIS HELPER EXISTS:
    To abstract away ChromaDB. Since ChromaDB is not installed locally,
    this class implements a semantic keyword overlap scoring method over
    an in-memory corporate knowledge base, simulating a vector database search.
    This guarantees that the agent works out-of-the-box with high-quality
    relevant articles, while remaining ready to integrate with ChromaDB in production.
    """

    def __init__(self) -> None:
        self._corpus = self._initialize_knowledge_base()

    def search(self, queries: list[str], top_k: int = 5) -> KnowledgeBundle:
        """
        Simulate embedding and vector retrieval by scoring Jaccard-overlap against tags.

        Tracks latency parameters for diagnostics metrics.

        Parameters
        ----------
        queries : list[str]
            Search strings compiled by KnowledgeQueryBuilder.
        top_k : int
            Number of documents to return.

        Returns
        -------
        KnowledgeBundle
        """
        start_time = time.monotonic()
        
        # Simulating embedding latency (e.g. calling an embedding API)
        embedding_latency_ms = 12.5 * len(queries)
        
        scored_docs: dict[str, float] = {}
        query_words = set()
        for q in queries:
            query_words.update(q.lower().split())

        # Scoring logic
        for doc in self._corpus:
            doc_words = set(doc.title.lower().split())
            for tag in doc.tags:
                doc_words.update(tag.lower().split())
            
            # Simple intersection score simulating vector cosine similarity
            intersection = query_words.intersection(doc_words)
            union = query_words.union(doc_words)
            
            if intersection:
                score = len(intersection) / len(union)
                # Keep highest score for this document
                scored_docs[doc.doc_id] = max(scored_docs.get(doc.doc_id, 0.0), score)

        # Sort documents by score descending
        sorted_results = sorted(scored_docs.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        retrieved_docs: list[RelevantDocument] = []
        doc_contents: dict[str, str] = {}
        total_score = 0.0

        for doc_id, score in sorted_results:
            doc = next(d for d in self._corpus if d.doc_id == doc_id)
            # Normalize score to [0.4, 0.95] to simulate vector similarity
            sim_score = 0.4 + (score * 0.55)
            retrieved_docs.append(RelevantDocument(
                doc_id=doc.doc_id,
                title=doc.title,
                type=doc.type,
                score=round(sim_score, 3)
            ))
            doc_contents[doc.doc_id] = doc.content
            total_score += sim_score

        avg_score = total_score / len(retrieved_docs) if retrieved_docs else 0.0
        search_latency_ms = (time.monotonic() - start_time) * 1000.0

        return KnowledgeBundle(
            documents=retrieved_docs,
            document_contents=doc_contents,
            average_score=round(avg_score, 3),
            embedding_latency_ms=round(embedding_latency_ms, 2),
            search_latency_ms=round(search_latency_ms, 2)
        )

    def _initialize_knowledge_base(self) -> list[KnowledgeDocument]:
        """
        Seed the mockup database with typical enterprise scenario documents.
        """
        return [
            KnowledgeDocument(
                doc_id="KB-PLAY-101",
                title="Database Latency & Query Timeout Escalation Playbook",
                doc_type="playbook",
                content=(
                    "Step 1: Check slow query logs. If query execution exceeds 5000ms, apply read replica routing.\n"
                    "Step 2: If timeouts occur on analytics/dashboard queries, direct customer to schedule reports "
                    "or partition time ranges to less than 30 days.\n"
                    "Step 3: Alert infrastructure operations if replica lag exceeds 60 seconds."
                ),
                tags=["slow", "latency", "timeout", "performance", "database", "replica", "dashboard", "reporting"]
            ),
            KnowledgeDocument(
                doc_id="KB-DOC-202",
                title="Analytics Dashboard Aggregations Configuration",
                doc_type="product_doc",
                content=(
                    "Our dashboards utilize real-time analytical engines. For high volume clients, queries must use "
                    "pre-aggregated views. Standard dashboard queries default to cached data (TTL: 15 minutes). "
                    "To force refresh, append the query parameter cache_bypass=true."
                ),
                tags=["dashboard", "analytics", "reporting", "cache", "performance", "aggregations"]
            ),
            KnowledgeDocument(
                doc_id="KB-GUIDE-303",
                title="Troubleshooting Slow Report Generaton and Timeout Failures",
                doc_type="troubleshooting_guide",
                content=(
                    "When users experience timeouts on report generation, verify query payload size:\n"
                    "1. Ensure filter criteria is narrowed. If query scans > 1 million records, SQL limits trigger automatic kill.\n"
                    "2. Disable sub-queries inside filter joins.\n"
                    "3. Suggest pre-aggregations as the primary remediation strategy."
                ),
                tags=["reporting", "slow", "timeout", "remediation", "troubleshooting", "sql", "limit"]
            ),
            KnowledgeDocument(
                doc_id="KB-LIMIT-404",
                title="Maximum Row Retrieval & Dashboard Limit Constraints",
                doc_type="limitation",
                content=(
                    "1. Maximum rows per analytical dashboard request: 100,000.\n"
                    "2. Maximum panels per single dashboard workspace: 25.\n"
                    "3. Long-running query timeout threshold: 30 seconds. Queries exceeding this are auto-cancelled."
                ),
                tags=["limit", "limitation", "timeout", "rows", "dashboard", "cancelled"]
            ),
            KnowledgeDocument(
                doc_id="KB-PRACTICE-505",
                title="Best Practices for Query Optimization and Pre-aggregation",
                doc_type="best_practice",
                content=(
                    "Best Practice 1: Always pre-aggregate metric fields (sum, avg) at database ingest.\n"
                    "Best Practice 2: Apply date partitions on queries. Keep window under 30 days for live charts.\n"
                    "Best Practice 3: Keep dashboard panels under 10 for latency under 2000ms."
                ),
                tags=["best_practice", "optimization", "pre-aggregation", "aggregations", "performance", "latency"]
            ),
            KnowledgeDocument(
                doc_id="KB-PLAY-606",
                title="Billing Disputes & Credit Application Playbook",
                doc_type="playbook",
                content=(
                    "For customer billing complaints or discrepancy reports:\n"
                    "1. Verify billing logs in Stripe/MySQL backend.\n"
                    "2. If discrepancies exist, sales reps can approve up to 10% credit without manager sign-off.\n"
                    "3. Escalations over $1000 require CFO approval."
                ),
                tags=["billing", "invoice", "charge", "discrepancy", "credit", "sales"]
            ),
            KnowledgeDocument(
                doc_id="KB-LIMIT-707",
                title="API Rate Limits and Request Policies",
                doc_type="limitation",
                content=(
                    "1. Inbound REST API limit: 1000 requests per minute per IP.\n"
                    "2. Burst limit: 200 requests per second. Exceeding triggers HTTP 429 Too Many Requests."
                ),
                tags=["rate_limit", "api", "limit", "429", "requests"]
            )
        ]


class KnowledgeContextBuilder:
    """
    Helper component responsible for organizing retrieved documents into categories.

    WHY THIS HELPER EXISTS:
    To format the retrieved corpus dynamically for prompt insertion, ensuring
    clear separation of playbooks, product information, limitations, guides, etc.
    """

    def build_context(self, document_contents: dict[str, str], documents: list[RelevantDocument]) -> dict[str, list[str]]:
        """
        Categorize documents into lists by their document type.

        Parameters
        ----------
        document_contents : dict[str, str]
            Map of doc_id -> content string.
        documents : list[RelevantDocument]
            Retrieved document metadata entries.

        Returns
        -------
        dict[str, list[str]]
            Categorized text segments.
        """
        context_data: dict[str, list[str]] = {
            "playbooks": [],
            "troubleshooting_guides": [],
            "previous_cases": [],
            "product_information": [],
            "known_limitations": [],
            "best_practices": []
        }

        type_mapping = {
            "playbook": "playbooks",
            "troubleshooting_guide": "troubleshooting_guides",
            "case": "previous_cases",
            "product_doc": "product_information",
            "limitation": "known_limitations",
            "best_practice": "best_practices"
        }

        for doc in documents:
            content = document_contents.get(doc.doc_id)
            if content:
                category = type_mapping.get(doc.type)
                if category:
                    formatted_text = f"[{doc.doc_id}] {doc.title}\n{content}"
                    context_data[category].append(formatted_text)

        return context_data


class KnowledgePromptBuilder:
    """
    Helper component responsible for compiling prompt parameters and rendering the final prompt.

    WHY THIS HELPER EXISTS:
    To wrap the generic PromptManager with RAG-specific parameters, avoiding hardcoded
    templating inside the core KnowledgeAgent.
    """

    def __init__(self, prompt_manager: Any, template_string: str) -> None:
        self._prompt_manager = prompt_manager
        self._template_string = template_string

    def build_prompt(
        self,
        customer_name: str,
        interaction_analysis: dict[str, Any],
        documents: list[RelevantDocument],
        document_contents: dict[str, str]
    ) -> str:
        """
        Assemble the template-ready string with groundedness restrictions.

        Parameters
        ----------
        customer_name : str
            Name of the customer context.
        interaction_analysis : dict[str, Any]
            The parsed InteractionAnalysis payload dictionary.
        documents : list[RelevantDocument]
            Retrieved metadata.
        document_contents : dict[str, str]
            Map of doc_id -> text content.

        Returns
        -------
        str
        """
        # Format the document contents block
        doc_blocks: list[str] = []
        for idx, doc in enumerate(documents, start=1):
            text = document_contents.get(doc.doc_id, "")
            block = f"Document [{idx}]:\n- ID: {doc.doc_id}\n- Title: {doc.title}\n- Type: {doc.type}\n- Content: {text}"
            doc_blocks.append(block)

        corpus_text = "\n\n".join(doc_blocks) if doc_blocks else "NO RELEVANT DOCUMENTS FOUND IN KNOWLEDGE BASE."

        # Prepare details for prompt injection
        issues_list = interaction_analysis.get("issues", [])
        issues_text = ", ".join(i.get("description", "") if isinstance(i, dict) else str(i) for i in issues_list)
        topics_text = ", ".join(interaction_analysis.get("key_topics", []))
        entities_list = interaction_analysis.get("entities", [])
        entities_text = ", ".join(e.get("name", "") if isinstance(e, dict) else str(e) for e in entities_list)

        return self._prompt_manager.render_string(
            self._template_string,
            customer_name=customer_name,
            interaction_summary=interaction_analysis.get("summary", "No summary available."),
            interaction_issues=issues_text or "None",
            interaction_topics=topics_text or "None",
            interaction_entities=entities_text or "None",
            knowledge_documents_text=corpus_text
        )


# ---------------------------------------------------------------------------
# Synthesis Prompt template — uses str.format_map-style placeholders.
# ---------------------------------------------------------------------------
_KNOWLEDGE_SYNTHESIS_PROMPT: str = """\
You are an expert Enterprise Knowledge Synthesis Analyst embedded in an \
agentic customer support platform.

Your task is to review the customer's situation (from the Interaction Analysis) \
and synthesize the provided organizational knowledge documents to answer the question:
"What does the organization already know about this customer's situation, and how can we resolve it?"

## Customer Context
- Customer/Company: {customer_name}

## Interaction Analysis (Inputs)
- Summary: {interaction_summary}
- Issues raised: {interaction_issues}
- Key Topics: {interaction_topics}
- Entities: {interaction_entities}

## Organizational Knowledge Corpus (Retrieved Documents)
{knowledge_documents_text}

## Required Output
You must synthesize the documents and return a structured JSON report. \
Do not add any conversational text or markdown code blocks outside the JSON.

{{
  "summary": "<synthesis of what is known about this issue and how the organization suggests solving it>",
  "confidence": <float in [0.0, 1.0] reflecting content coverage and relevance>,
  "relevant_documents": [
    {{
      "doc_id": "<document ID>",
      "title": "<document title>",
      "type": "<playbook | product_doc | troubleshooting_guide | case | limitation | best_practice>",
      "score": <float relevance score>
    }}
  ]
}}

## Knowledge groundedness safety rules:
1. Use ONLY the provided knowledge corpus. NEVER invent or assume facts.
2. NEVER mention playbooks, guides, limitations, or best practices that are not present in the provided corpus.
3. If no relevant documents are provided or the corpus is empty, set confidence to 0.0, state that no internal documentation was found, and return an empty list for relevant_documents.
4. Return STRICT JSON only.
"""

_SYSTEM_PROMPT: str = (
    "You are a structured JSON knowledge synthesis engine. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)


# =============================================================================
# Section 3: The Agent
# =============================================================================


class KnowledgeAgent(BaseAgent):
    """
    KnowledgeAgent is responsible for retrieving and synthesizing organizational knowledge
    relevant to customer interactions.

    Planner metadata
    ----------------
    * ``required_inputs`` — requires `analysis.interaction_analysis` (produced by InteractionAgent).
    * ``produced_outputs`` — generates `context.knowledge_context`.
    """

    agent_name: ClassVar[str] = "KnowledgeAgent"

    description: ClassVar[str] = (
        "Retrieves and synthesizes enterprise playbooks, guides, and policies "
        "relevant to interaction intelligence to build a grounded knowledge bundle."
    )

    required_inputs: ClassVar[list[str]] = [
        "analysis.interaction_analysis"
    ]

    produced_outputs: ClassVar[list[str]] = [
        "context.knowledge_context"
    ]

    supported_execution_modes: ClassVar[list[str]] = [
        "LIVE",
        "DEBUG",
        "DRY_RUN",
        "SIMULATION",
    ]

    priority: ClassVar[int] = 90
    """
    Priority 90. Dispatched after InteractionAgent (100) because it relies on
    the interaction summary, issues, and topics to perform vector searches.
    """

    _LLM_TEMPERATURE: ClassVar[float] = 0.1
    _LLM_MAX_TOKENS: ClassVar[int] = 4096

    # =========================================================================
    # Constructor
    # =========================================================================

    def __init__(
        self,
        llm_service=None,
        prompt_manager=None,
        state_validator=None,
        response_parser: ResponseParser | None = None,
        query_builder: KnowledgeQueryBuilder | None = None,
        knowledge_service: KnowledgeService | None = None,
        context_builder: KnowledgeContextBuilder | None = None,
        prompt_builder: KnowledgePromptBuilder | None = None,
    ) -> None:
        super().__init__(
            llm_service=llm_service,
            prompt_manager=prompt_manager,
            state_validator=state_validator,
        )
        self._parser: ResponseParser = response_parser or ResponseParser()
        self._query_builder = query_builder or KnowledgeQueryBuilder()
        self._service = knowledge_service or KnowledgeService()
        self._context_builder = context_builder or KnowledgeContextBuilder()
        self._prompt_builder = prompt_builder or KnowledgePromptBuilder(
            prompt_manager=self.prompts,
            template_string=_KNOWLEDGE_SYNTHESIS_PROMPT
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
        Verify that interaction analysis exists and contains valid elements.
        """
        analysis = state.analysis.interaction_analysis
        if not analysis:
            raise ValueError(
                "KnowledgeAgent requires 'analysis.interaction_analysis' but it is missing or empty."
            )
        self._logger.debug(
            "[KnowledgeAgent] Input validation passed — interaction_analysis is populated."
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
        Orchestrate search query building, vector retrieval, context compiling,
        LLM synthesis, and state update.
        """
        self._logger.info(
            "[KnowledgeAgent] Starting knowledge synthesis | request_id=%s",
            context.request_id,
        )

        interaction_analysis = state.analysis.interaction_analysis

        # ── Step 1: Build semantic queries ──────────────────────────────────
        queries = self._query_builder.build_queries(interaction_analysis)
        self._logger.info(
            "[KnowledgeAgent] Generated %d semantic search queries: %s",
            len(queries), queries
        )

        # ── Step 2: Vector search retrieval (delegated to KnowledgeService) ──
        bundle = self._service.search(queries, top_k=5)
        self._logger.info(
            "[KnowledgeAgent] Search complete — retrieved %d documents | avg_score=%s",
            len(bundle.documents), bundle.average_score
        )

        self._record_metric("embedding_latency_ms", bundle.embedding_latency_ms)
        self._record_metric("vector_search_latency_ms", bundle.search_latency_ms)
        self._record_metric("documents_retrieved", len(bundle.documents))
        self._record_metric("documents_ranked", len(bundle.documents))
        self._record_metric("average_similarity_score", bundle.average_score)

        # ── Step 3: Organize context ────────────────────────────────────────
        categorized_context = self._context_builder.build_context(
            bundle.document_contents, bundle.documents
        )

        # ── Step 4: Build Prompt ─────────────────────────────────────────────
        customer_name = state.customer.customer_name or "Unknown Customer"
        prompt = self._prompt_builder.build_prompt(
            customer_name=customer_name,
            interaction_analysis=interaction_analysis,
            documents=bundle.documents,
            document_contents=bundle.document_contents
        )
        self._logger.debug(
            "[KnowledgeAgent] Prompt generated — length=%d chars", len(prompt)
        )

        # ── Step 5: Call LLM ─────────────────────────────────────────────────
        self._logger.info("[KnowledgeAgent] Submitting knowledge synthesis to LLM.")
        llm_start = time.monotonic()
        
        pipeline_response = await self.llm.generate_text(
            raw_prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=self._LLM_TEMPERATURE,
            max_tokens=self._LLM_MAX_TOKENS,
            cache_enabled=True
        )
        
        llm_latency_ms = (time.monotonic() - llm_start) * 1000.0
        self._record_llm_call()
        self._record_metric("llm_latency_ms", round(llm_latency_ms, 2))
        self._record_metric("prompt_tokens", pipeline_response.prompt_tokens)
        self._record_metric("output_tokens", pipeline_response.output_tokens)
        
        self._logger.info(
            "[KnowledgeAgent] LLM completed | latency_ms=%.1f tokens=%d+%d",
            llm_latency_ms, pipeline_response.prompt_tokens, pipeline_response.output_tokens
        )

        # ── Step 6: Parse LLM synthesis ──────────────────────────────────────
        knowledge_ctx = self._parse_response(
            pipeline_response.text, bundle.documents
        )
        self._logger.info("[KnowledgeAgent] Synthesized knowledge parsed successfully.")
        self._record_metric("knowledge_confidence", knowledge_ctx.confidence)

        # ── Step 7: Post-process & Validate ──────────────────────────────────
        knowledge_ctx = self._validate_synthesis(knowledge_ctx, bundle.documents)

        # ── Step 8: Update state ─────────────────────────────────────────────
        self._write_state(state, knowledge_ctx)
        self._logger.info(
            "[KnowledgeAgent] WorkflowState updated — knowledge_context written."
        )

        return AgentResult.success_result(
            agent_name=self.agent_name,
            execution_time_ms=0.0,  # Overwritten by BaseAgent
            output_data=knowledge_ctx.model_dump(mode="json"),
            confidence=knowledge_ctx.confidence,
            message=(
                f"Knowledge search completed. Retrieved {len(bundle.documents)} documents. "
                f"Confidence = {knowledge_ctx.confidence:.2f}."
            )
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
        Attempt lightweight recovery on LLM parsing issues.
        """
        if isinstance(exc, LLMJSONParseError):
            self._logger.warning(
                "[KnowledgeAgent] JSON parse failure — returning fallback stub. request_id=%s",
                context.request_id
            )
            stub = KnowledgeContext(
                summary="[KnowledgeAgent failed to parse LLM response — raw information unavailable]",
                confidence=0.0,
            )
            try:
                self._write_state(state, stub)
            except Exception as write_exc:  # noqa: BLE001
                self._logger.error("[KnowledgeAgent] Stub write failed: %s", write_exc)

            return AgentResult.failure_result(
                agent_name=self.agent_name,
                execution_time_ms=0.0,
                errors=[
                    f"LLMJSONParseError: {exc}",
                    "Knowledge synthesis could not be completed."
                ],
                message="LLM returned malformed JSON; recovery stub written to state."
            )

        return None

    # =========================================================================
    # Private processing methods
    # =========================================================================

    def _parse_response(
        self,
        raw_text: str,
        retrieved_docs: list[RelevantDocument],
    ) -> KnowledgeContext:
        """
        Parse raw text into strongly-typed KnowledgeContext, enriching it with
        retrieved document metadata.
        """
        self._logger.debug("[KnowledgeAgent] Parsing response...")
        knowledge_ctx = self._parser.parse_json_as(raw_text, KnowledgeContext)

        # Override relevant_documents from the authoritative retrieval results
        # rather than trusting the LLM's self-reported list.
        knowledge_ctx = knowledge_ctx.model_copy(update={
            "relevant_documents": retrieved_docs,
        })

        return knowledge_ctx

    def _validate_synthesis(
        self,
        knowledge_ctx: KnowledgeContext,
        retrieved_docs: list[RelevantDocument]
    ) -> KnowledgeContext:
        """
        Apply groundedness constraints and validate summary.
        """
        # Fallback summary if empty
        summary = knowledge_ctx.summary.strip()
        if not summary:
            summary = f"Retrieved {len(retrieved_docs)} relevant documentation articles regarding issues."
            self._add_warning("LLM returned an empty summary — synthesized custom report.")

        return knowledge_ctx.model_copy(update={
            "summary": summary
        })

    def _write_state(self, state: WorkflowState, knowledge_ctx: KnowledgeContext) -> None:
        """
        Write results only to WorkflowState.context.knowledge_context.
        """
        state.context.knowledge_context = [
            doc.model_dump(mode="json") for doc in knowledge_ctx.relevant_documents
        ]
        
        state.context.knowledge_context.append({
            "summary": knowledge_ctx.summary,
            "confidence": knowledge_ctx.confidence,
        })
