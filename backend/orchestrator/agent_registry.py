"""
backend/orchestrator/agent_registry.py
======================================
AgentRegistry is the central repository for discovery, validation, and instantiation 
of all business agents in the InsightFlow AI platform.

It acts as the single source of truth for agent classes. It enforces strict metadata 
validation at registration time, ensures thread safety, supports dynamic locking lifecycles, 
and leverages dependency injection for clean instantiation.
"""

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Any, Callable, ClassVar, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# =============================================================================
# Section 1: Custom Orchestration Exceptions
# =============================================================================

class RegistrationError(Exception):
    """Base exception for all registry-related errors."""
    pass


class DuplicateAgentRegistrationError(RegistrationError):
    """Raised when trying to register an agent that already exists in the registry."""
    pass


class UnknownAgentError(RegistrationError):
    """Raised when looking up or instantiating an agent that is not registered."""
    pass


class InvalidAgentMetadataError(RegistrationError):
    """Raised when an agent class fails validation checks."""
    pass


class RegistryLockedError(RegistrationError):
    """Raised when trying to mutate the registry while it is in LOCKED state."""
    pass


# =============================================================================
# Section 2: Metadata & State Models
# =============================================================================

class RegistryState(Enum):
    """Lifecycle stages of the registry."""
    OPEN = "OPEN"
    LOCKED = "LOCKED"


class AgentMetadata(BaseModel):
    """
    Strongly typed model representing an agent's structural metadata.
    """
    agent_name: str = Field(description="Canonical unique agent identifier.")
    description: str = Field(description="Brief explanation of the agent's purpose.")
    priority: int = Field(description="Execution priority tier.")
    required_inputs: List[str] = Field(default_factory=list, description="Input state paths required.")
    produced_outputs: List[str] = Field(default_factory=list, description="State paths updated by execution.")


# =============================================================================
# Section 3: The Registry Implementation
# =============================================================================

class AgentRegistry:
    """
    Thread-safe registry for managing agent classes lifecycle.
    """
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._registry: Dict[str, Type[BaseAgent]] = {}
        # Maintain deterministic registration order
        self._registration_order: List[str] = []
        self._state: RegistryState = RegistryState.OPEN

    @property
    def state(self) -> RegistryState:
        """Returns the current registry lifecycle state."""
        return self._state

    def lock_registry(self) -> None:
        """
        Locks the registry to prevent further mutations during executions.
        """
        with self._lock:
            self._state = RegistryState.LOCKED
            logger.info("[AgentRegistry] Registry transitioned to LOCKED state.")

    def unlock_registry(self) -> None:
        """
        Unlocks the registry to allow mutations.
        """
        with self._lock:
            self._state = RegistryState.OPEN
            logger.info("[AgentRegistry] Registry transitioned to OPEN state.")

    def _assert_open(self) -> None:
        """Helper to raise RegistryLockedError if locked."""
        if self._state == RegistryState.LOCKED:
            raise RegistryLockedError("Registry modifications are prohibited while locked.")

    def _validate_agent_class(self, agent_class: Type[BaseAgent]) -> None:
        """
        Validates agent metadata and implementation details before registration.
        """
        if not issubclass(agent_class, BaseAgent):
            raise InvalidAgentMetadataError(
                f"Class '{agent_class.__name__}' must inherit from BaseAgent."
            )

        # 1. agent_name
        name = getattr(agent_class, "agent_name", None)
        if not name or not isinstance(name, str) or not name.strip() or name == "BaseAgent":
            raise InvalidAgentMetadataError(
                f"Agent class '{agent_class.__name__}' must define a unique non-empty string 'agent_name' different from 'BaseAgent'."
            )

        # 2. required_inputs
        req_in = getattr(agent_class, "required_inputs", None)
        if req_in is None or not isinstance(req_in, list):
            raise InvalidAgentMetadataError(
                f"Agent class '{agent_class.__name__}' must define a list of 'required_inputs'."
            )

        # 3. produced_outputs
        prod_out = getattr(agent_class, "produced_outputs", None)
        if prod_out is None or not isinstance(prod_out, list):
            raise InvalidAgentMetadataError(
                f"Agent class '{agent_class.__name__}' must define a list of 'produced_outputs'."
            )

        # 4. priority
        priority = getattr(agent_class, "priority", None)
        if priority is None or not isinstance(priority, int):
            raise InvalidAgentMetadataError(
                f"Agent class '{agent_class.__name__}' must define an integer 'priority'."
            )

        # 5. execute() implementation
        execute_fn = getattr(agent_class, "execute", None)
        if not execute_fn or not callable(execute_fn):
            raise InvalidAgentMetadataError(
                f"Agent class '{agent_class.__name__}' must implement 'execute'."
            )
        if getattr(execute_fn, "__isabstractmethod__", False):
            raise InvalidAgentMetadataError(
                f"Agent class '{agent_class.__name__}' cannot have an abstract 'execute' method."
            )

    # ── Mutation Operations ──────────────────────────────────────────────────

    def register(self, agent_class: Type[BaseAgent]) -> None:
        """
        Registers a single BaseAgent class in a thread-safe manner.
        """
        with self._lock:
            self._assert_open()
            self._validate_agent_class(agent_class)
            
            name = agent_class.agent_name
            if name in self._registry:
                logger.warning("[AgentRegistry] Duplicate registration attempt for '%s'", name)
                raise DuplicateAgentRegistrationError(f"Agent '{name}' is already registered.")

            self._registry[name] = agent_class
            self._registration_order.append(name)
            logger.info("[AgentRegistry] Agent Registered: %s", name)

    def register_many(self, agent_classes: List[Type[BaseAgent]]) -> None:
        """
        Registers multiple BaseAgent classes.
        """
        # Register each class individually to leverage lock and validation
        for agent_class in agent_classes:
            self.register(agent_class)

    def unregister(self, agent_name: str) -> None:
        """
        Removes an agent class from the registry.
        """
        with self._lock:
            self._assert_open()
            if agent_name not in self._registry:
                raise UnknownAgentError(f"Agent '{agent_name}' is not registered.")

            self._registry.pop(agent_name)
            if agent_name in self._registration_order:
                self._registration_order.remove(agent_name)
            logger.info("[AgentRegistry] Agent Unregistered: %s", agent_name)

    def clear(self) -> None:
        """
        Clears all registered agent classes.
        """
        with self._lock:
            self._assert_open()
            self._registry.clear()
            self._registration_order.clear()
            logger.info("[AgentRegistry] Registry Cleared")

    # ── Read Operations ──────────────────────────────────────────────────────

    def exists(self, agent_name: str) -> bool:
        """Checks if an agent is registered."""
        with self._lock:
            return agent_name in self._registry

    def get(self, agent_name: str) -> Type[BaseAgent]:
        """Retrieves a registered agent class."""
        with self._lock:
            if agent_name not in self._registry:
                raise UnknownAgentError(f"Agent '{agent_name}' is not registered.")
            return self._registry[agent_name]

    def get_all(self) -> List[Type[BaseAgent]]:
        """Retrieves all registered agent classes in deterministic order."""
        with self._lock:
            return [self._registry[name] for name in self._registration_order]

    def list_agent_names(self) -> List[str]:
        """Returns list of registered agent names in deterministic order."""
        with self._lock:
            return list(self._registration_order)

    def count(self) -> int:
        """Returns the number of registered agents."""
        with self._lock:
            return len(self._registry)

    # ── Instantiation ────────────────────────────────────────────────────────

    def create_instance(
        self,
        agent_name: str,
        llm_service: Optional[Any] = None,
        prompt_manager: Optional[Any] = None,
        state_validator: Optional[Any] = None
    ) -> BaseAgent:
        """
        Instantiates a registered agent using dependency injection.
        """
        agent_class = self.get(agent_name)
        return agent_class(
            llm_service=llm_service,
            prompt_manager=prompt_manager,
            state_validator=state_validator
        )

    # ── Metadata ─────────────────────────────────────────────────────────────

    def get_metadata(self, agent_name: str) -> AgentMetadata:
        """
        Returns strongly typed metadata for the specified agent.
        """
        agent_class = self.get(agent_name)
        meta = agent_class.get_agent_metadata()
        return AgentMetadata(
            agent_name=meta["agent_name"],
            description=meta["description"],
            priority=meta["priority"],
            required_inputs=meta["required_inputs"],
            produced_outputs=meta["produced_outputs"]
        )

    def get_all_metadata(self) -> List[AgentMetadata]:
        """
        Returns strongly typed metadata list in deterministic registration order.
        """
        names = self.list_agent_names()
        return [self.get_metadata(name) for name in names]

    # ── Debugging & Execution Reports ────────────────────────────────────────

    def snapshot(self) -> Dict[str, Type[BaseAgent]]:
        """
        Returns an immutable view/copy of the current registry mapping.
        """
        with self._lock:
            return dict(self._registry)

    # ── Future Extensibility Stubs ───────────────────────────────────────────

    def discover_plugins(self, directory_path: str) -> None:
        """
        Extension point: scan directory and load agent subclasses dynamically.
        """
        pass

    def register_conditional(
        self, 
        agent_class: Type[BaseAgent], 
        condition: Callable[[], bool]
    ) -> None:
        """
        Extension point: register agent only if condition evaluates to True.
        """
        pass
