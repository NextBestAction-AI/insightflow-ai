"""
backend/services/llm/mock_client.py
===================================
Production-grade Mock LLM provider client.

Implements the BaseLLMClient interface, responding with deterministic and
consistent mock JSON payloads for every business agent in the InsightFlow AI platform.
"""

from __future__ import annotations

import asyncio
import random
import logging
from typing import Any

from backend.services.llm.base_client import BaseLLMClient, LLMRequest, LLMRawResponse
from backend.services.llm.config import LLMConfig
from backend.services.llm.mock_responses import (
    interaction_response,
    knowledge_response,
    crm_response,
    health_response,
    risk_response,
    reasoning_response,
    recommendation_response
)

logger = logging.getLogger(__name__)


class MockLLMClient(BaseLLMClient):
    """
    Mock LLM Client simulating a real LLM provider (like Gemini or OpenAI).

    Returns realistic, deterministic, and internally consistent mock responses
    for every business agent. Simulates configurable latency and preserves
    usage tracking, caching, and retry logic.
    """

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(provider_name="mock")
        self._config = config
        logger.info("MockLLMClient initialized.")

    async def generate(self, request: LLMRequest) -> LLMRawResponse:
        """Simulate generate text API call with realistic latency. Returns mock JSON since agents expect JSON text."""
        # 1. Simulate configurable latency (100 - 300 ms)
        latency_ms = random.uniform(100.0, 300.0)
        await asyncio.sleep(latency_ms / 1000.0)

        # 2. Get mock JSON response
        response_text = self._get_mock_json(request)

        # 3. Compile raw response DTO
        prompt_tokens = len(request.prompt.split())
        output_tokens = len(response_text.split())

        return LLMRawResponse(
            text=response_text,
            model="mock-model-v1",
            provider="mock",
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            finish_reason="STOP",
            raw_metadata={"latency_ms": latency_ms, "mocked": True}
        )

    async def generate_json(self, request: LLMRequest) -> LLMRawResponse:
        """Simulate generate structured JSON API call with realistic latency."""
        # 1. Simulate configurable latency (100 - 300 ms)
        latency_ms = random.uniform(100.0, 300.0)
        await asyncio.sleep(latency_ms / 1000.0)

        # 2. Get JSON response
        response_json = self._get_mock_json(request)

        # 3. Compile raw response DTO
        prompt_tokens = len(request.prompt.split())
        output_tokens = len(response_json.split())

        return LLMRawResponse(
            text=response_json,
            model="mock-model-v1",
            provider="mock",
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            finish_reason="STOP",
            raw_metadata={"latency_ms": latency_ms, "mocked": True}
        )

    async def health_check(self) -> bool:
        """Always healthy."""
        return True

    def _get_mock_json(self, request: LLMRequest) -> str:
        """Select and return the appropriate mock JSON based on structured indicators or keywords."""
        # 1. Structured indicators: check metadata
        agent_id = request.metadata.get("agent") or request.metadata.get("task")
        if agent_id:
            agent_id = str(agent_id).lower()
            if "interaction" in agent_id:
                return interaction_response(request.prompt)
            if "knowledge" in agent_id:
                return knowledge_response(request.prompt)
            if "crm" in agent_id:
                return crm_response(request.prompt)
            if "health" in agent_id:
                return health_response(request.prompt)
            if "risk" in agent_id:
                return risk_response(request.prompt)
            if "reasoning" in agent_id:
                return reasoning_response(request.prompt)
            if "recommendation" in agent_id:
                return recommendation_response(request.prompt)

        # 2. Check system prompt (more structured than raw prompt keywords)
        sys_prompt = (request.system_prompt or "").lower()
        if "interaction" in sys_prompt or "sentiment" in sys_prompt:
            return interaction_response(request.prompt)
        if "knowledge" in sys_prompt or "relevantdocument" in sys_prompt:
            return knowledge_response(request.prompt)
        if "crm" in sys_prompt:
            return crm_response(request.prompt)
        if "health" in sys_prompt or "healthassessment" in sys_prompt:
            return health_response(request.prompt)
        if "risk" in sys_prompt or "riskassessment" in sys_prompt:
            return risk_response(request.prompt)
        if "reasoning" in sys_prompt or "businessreasoning" in sys_prompt:
            return reasoning_response(request.prompt)
        if "recommendation" in sys_prompt or "recommendationplan" in sys_prompt:
            return recommendation_response(request.prompt)

        # 3. Fallback: prompt keyword matching
        prompt = request.prompt.lower()
        if "interaction" in prompt or "sentiment" in prompt:
            return interaction_response(request.prompt)
        if "knowledge" in prompt or "relevant_documents" in prompt:
            return knowledge_response(request.prompt)
        if "crm" in prompt:
            return crm_response(request.prompt)
        if "health" in prompt or "health_assessment" in prompt:
            return health_response(request.prompt)
        if "risk" in prompt or "risk_assessment" in prompt:
            return risk_response(request.prompt)
        if "reasoning" in prompt or "business_reasoning" in prompt:
            return reasoning_response(request.prompt)
        if "recommendation" in prompt or "recommendation_plan" in prompt:
            return recommendation_response(request.prompt)

        # Final default: return interaction analysis
        return interaction_response(request.prompt)
