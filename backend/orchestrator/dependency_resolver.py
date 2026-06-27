# -*- coding: utf-8 -*-
"""
backend/orchestrator/dependency_resolver.py
===========================================
DependencyResolver is responsible for discovering execution dependencies 
between registered business agents by analyzing their metadata.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)

# =============================================================================
# Section 1: Custom Exceptions
# =============================================================================

class DependencyResolutionError(Exception):
    """Base exception for all dependency resolution errors."""
    pass

class MissingDependencyError(DependencyResolutionError):
    """Raised when an agent requires an input that is not produced or in initial state."""
    pass

class DuplicateProducerError(DependencyResolutionError):
    """Raised when multiple agents produce the same state output path."""
    pass

class CircularDependencyError(DependencyResolutionError):
    """Raised when circular dependencies exist between registered agents."""
    pass

class InvalidDependencyGraphError(DependencyResolutionError):
    """Raised when the constructed dependency graph fails structural validation checks."""
    pass


# =============================================================================
# Section 2: Output Models
# =============================================================================

class DependencyType(str, Enum):
    """Types of dependencies between agents."""
    REQUIRED = "Required"
    OPTIONAL = "Optional"
    CONDITIONAL = "Conditional"


class DependencyEdge(BaseModel):
    """A directed edge in the dependency graph representing state production and consumption."""
    model_config = ConfigDict(frozen=True)

    producer: str = Field(description="Name of the agent producing the output.")
    consumer: str = Field(description="Name of the agent consuming the output.")
    shared_state: str = Field(description="The dotted path of the shared state attribute.")
    dependency_type: DependencyType = Field(
        default=DependencyType.REQUIRED,
        description="Execution requirement mapping of this dependency."
    )


class DependencyNode(BaseModel):
    """A node in the dependency graph wrapping an agent and its direct connections."""
    model_config = ConfigDict(frozen=True)

    agent_name: str = Field(description="Canonical name of the registered agent.")
    metadata: Any = Field(description="The underlying AgentMetadata instance.")
    incoming: List[str] = Field(
        default_factory=list,
        description="Names of predecessor agents that must run before this agent."
    )
    outgoing: List[str] = Field(
        default_factory=list,
        description="Names of successor agents that depend on this agent."
    )


class ExecutionLevel(BaseModel):
    """An execution stage containing parallelizable agents."""
    model_config = ConfigDict(frozen=True)

    level_number: int = Field(description="Sequential stage index.")
    agents: List[str] = Field(description="Deterministic sorted list of agent names in this level.")
    parallel: bool = Field(description="Whether multiple agents exist at this level and can execute in parallel.")


class GraphStatistics(BaseModel):
    """Metrics and statistics summarizing the topology of the dependency graph."""
    model_config = ConfigDict(frozen=True)

    node_count: int = Field(description="Total number of nodes (agents) in the graph.")
    edge_count: int = Field(description="Total number of dependency edges in the graph.")
    levels_count: int = Field(description="Number of execution levels (depth of the graph).")
    root_agents: List[str] = Field(description="Agents that have no incoming dependencies.")
    leaf_agents: List[str] = Field(description="Agents that have no outgoing dependencies.")
    parallelizable_groups: List[List[str]] = Field(
        description="Groups of agents that can execute concurrently at each level."
    )


class DependencyGraph(BaseModel):
    """Immutable representation of the resolved, validated agent dependency graph."""
    model_config = ConfigDict(frozen=True)

    nodes: Dict[str, DependencyNode] = Field(description="Map of agent name to its dependency node.")
    edges: List[DependencyEdge] = Field(description="List of all directed edges in the graph.")
    root_agents: List[str] = Field(description="List of entry-point agents with zero dependencies.")
    leaf_agents: List[str] = Field(description="List of terminal-point agents.")
    levels: List[ExecutionLevel] = Field(description="Execution level stages sorted deterministically.")
    statistics: GraphStatistics = Field(description="Summary metrics of the dependency graph.")


class AgentMetadataWithDuration(BaseModel):
    """Extends AgentMetadata to include estimated execution time."""
    model_config = ConfigDict(frozen=True)

    agent_name: str = Field(description="Canonical unique agent identifier.")
    description: str = Field(description="Brief explanation of the agent's purpose.")
    priority: int = Field(description="Execution priority tier.")
    required_inputs: List[str] = Field(default_factory=list, description="Input state paths required.")
    produced_outputs: List[str] = Field(default_factory=list, description="State paths updated by execution.")
    estimated_execution_ms: float = Field(default=500.0, description="Estimated agent execution duration in ms.")


class AgentMetadataCollection(BaseModel):
    """A collection of extracted metadata from registered agents."""
    model_config = ConfigDict(frozen=True)

    agents: List[Any] = Field(description="List of AgentMetadataWithDuration objects.")
    count: int = Field(description="Total count of agents in the collection.")


class ValidationReport(BaseModel):
    """Structured report detailing the results of structural validations on the graph."""
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warning messages.")
    errors: List[str] = Field(default_factory=list, description="Fatal validation error messages.")
    orphan_agents: List[str] = Field(default_factory=list, description="Agents completely disconnected from the graph.")
    duplicate_outputs: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Output paths that have duplicate registered producers."
    )
    disconnected_components: List[List[str]] = Field(
        default_factory=list,
        description="Groups of disconnected subgraphs."
    )

    @property
    def is_valid(self) -> bool:
        """Returns True if the validation contains zero fatal errors."""
        return len(self.errors) == 0


# =============================================================================
# Section 3: Helper Components
# =============================================================================

class MetadataExtractor:
    """Extracts and normalizes metadata from AgentRegistry."""

    @staticmethod
    def extract(registry: Any) -> AgentMetadataCollection:
        """Queries registry metadata and returns a normalized collection enriched with durations."""
        agents_meta = []
        for name in registry.list_agent_names():
            agent_class = registry.get(name)
            meta = registry.get_metadata(name)
            dur = getattr(agent_class, "estimated_execution_ms", 500.0)
            agents_meta.append(AgentMetadataWithDuration(
                agent_name=meta.agent_name,
                description=meta.description,
                priority=meta.priority,
                required_inputs=meta.required_inputs,
                produced_outputs=meta.produced_outputs,
                estimated_execution_ms=dur
            ))
        return AgentMetadataCollection(
            agents=agents_meta,
            count=len(agents_meta)
        )


class DependencyGraphBuilder:
    """Constructs a directed graph of agent dependencies using metadata."""

    @staticmethod
    def build(metadata_collection: AgentMetadataCollection) -> Tuple[Dict[str, DependencyNode], List[DependencyEdge]]:
        """Builds graph nodes and edges mapping producers to consumers."""
        # Map produced output path to the agent producing it
        output_to_producer: Dict[str, str] = {}
        for agent_meta in metadata_collection.agents:
            for out in agent_meta.produced_outputs:
                if out not in output_to_producer:
                    output_to_producer[out] = agent_meta.agent_name

        edges: List[DependencyEdge] = []
        for agent_meta in metadata_collection.agents:
            consumer = agent_meta.agent_name
            for req in agent_meta.required_inputs:
                producer = output_to_producer.get(req)
                if producer:
                    edge = DependencyEdge(
                        producer=producer,
                        consumer=consumer,
                        shared_state=req,
                        dependency_type=DependencyType.REQUIRED
                    )
                    edges.append(edge)

        incoming_map: Dict[str, Set[str]] = {a.agent_name: set() for a in metadata_collection.agents}
        outgoing_map: Dict[str, Set[str]] = {a.agent_name: set() for a in metadata_collection.agents}

        for edge in edges:
            incoming_map[edge.consumer].add(edge.producer)
            outgoing_map[edge.producer].add(edge.consumer)

        nodes: Dict[str, DependencyNode] = {}
        for agent_meta in metadata_collection.agents:
            name = agent_meta.agent_name
            nodes[name] = DependencyNode(
                agent_name=name,
                metadata=agent_meta,
                incoming=sorted(list(incoming_map[name])),
                outgoing=sorted(list(outgoing_map[name]))
            )

        return nodes, edges


class DependencyGraphValidator:
    """Validates the structural integrity of the dependency graph."""

    def __init__(self, promote_orphan_warnings_to_errors: bool = False) -> None:
        self.promote_orphan_warnings_to_errors = promote_orphan_warnings_to_errors

    def validate(
        self,
        metadata_collection: AgentMetadataCollection,
        nodes: Dict[str, DependencyNode],
        edges: List[DependencyEdge]
    ) -> ValidationReport:
        """Performs validation checks to detect invalid registry metadata or topological bugs."""
        report = ValidationReport()

        # 1. Duplicate Agent Names
        seen_names = set()
        for agent_meta in metadata_collection.agents:
            if agent_meta.agent_name in seen_names:
                report.errors.append(f"Duplicate agent name registered: '{agent_meta.agent_name}'")
            seen_names.add(agent_meta.agent_name)

        # 2. Duplicate Producers
        output_producers: Dict[str, List[str]] = {}
        for agent_meta in metadata_collection.agents:
            for out in agent_meta.produced_outputs:
                output_producers.setdefault(out, []).append(agent_meta.agent_name)

        for out, producers in output_producers.items():
            if len(producers) > 1:
                report.duplicate_outputs[out] = producers
                report.errors.append(
                    f"Duplicate producers detected for output path '{out}': produced by {producers}"
                )

        # 3. Missing Producer
        initial_prefixes = ("input.", "customer.", "context.")
        for agent_meta in metadata_collection.agents:
            for req in agent_meta.required_inputs:
                has_producer = req in output_producers
                is_initial = req.startswith(initial_prefixes)
                if not has_producer and not is_initial:
                    report.errors.append(
                        f"Missing producer: Agent '{agent_meta.agent_name}' requires input '{req}', "
                        f"which is neither produced by any registered agent nor a known initial state input path."
                    )

        # 4. Circular Dependencies
        visited: Dict[str, int] = {name: 0 for name in nodes}  # 0=unvisited, 1=visiting, 2=visited
        cycles: List[List[str]] = []

        def dfs(node_name: str, path: List[str]):
            visited[node_name] = 1
            path.append(node_name)

            for neighbor in nodes[node_name].outgoing:
                if visited[neighbor] == 1:
                    cycle_start = path.index(neighbor)
                    cycle_path = path[cycle_start:] + [neighbor]
                    cycles.append(cycle_path)
                elif visited[neighbor] == 0:
                    dfs(neighbor, path)

            path.pop()
            visited[node_name] = 2

        for name in nodes:
            if visited[name] == 0:
                dfs(name, [])

        for cycle in cycles:
            report.errors.append(f"Circular dependency detected: {' -> '.join(cycle)}")

        # 5. Disconnected / Orphan Agents
        for name, node in nodes.items():
            if len(node.incoming) == 0 and len(node.outgoing) == 0:
                report.orphan_agents.append(name)
                msg = f"Orphan agent detected: '{name}' has no dependencies and is not consumed by any other agent."
                if self.promote_orphan_warnings_to_errors:
                    report.errors.append(msg)
                else:
                    report.warnings.append(msg)

        # 6. Disconnected Components
        visited_undirected = set()
        components = []
        adj_undirected: Dict[str, Set[str]] = {name: set() for name in nodes}

        for name, node in nodes.items():
            for parent in node.incoming:
                adj_undirected[name].add(parent)
                adj_undirected[parent].add(name)
            for child in node.outgoing:
                adj_undirected[name].add(child)
                adj_undirected[child].add(name)

        for name in nodes:
            if name not in visited_undirected:
                comp = []
                queue = [name]
                visited_undirected.add(name)
                while queue:
                    curr = queue.pop(0)
                    comp.append(curr)
                    for neighbor in adj_undirected[curr]:
                        if neighbor not in visited_undirected:
                            visited_undirected.add(neighbor)
                            queue.append(neighbor)
                components.append(sorted(comp))

        if len(components) > 1:
            report.disconnected_components = components
            report.warnings.append(
                f"Graph contains {len(components)} disconnected components: {components}"
            )

        return report


# =============================================================================
# Section 4: Main DependencyResolver
# =============================================================================

class DependencyResolver:
    """Coordinates metadata extraction, topological resolution, and cache management."""

    def __init__(self, promote_orphan_warnings_to_errors: bool = False) -> None:
        self.promote_orphan_warnings_to_errors = promote_orphan_warnings_to_errors
        self._cached_signature: Optional[Tuple] = None
        self._cached_graph: Optional[DependencyGraph] = None

    def invalidate_cache(self) -> None:
        """Explicitly clear the cached dependency graph."""
        self._cached_signature = None
        self._cached_graph = None
        logger.info("[DependencyResolver] Graph cache explicitly invalidated")

    def _generate_signature(self, metadata_collection: AgentMetadataCollection) -> Tuple:
        """Generates a deterministic signature tuple of the registry metadata state."""
        signature_items = []
        for meta in metadata_collection.agents:
            signature_items.append((
                meta.agent_name,
                meta.priority,
                tuple(sorted(meta.required_inputs)),
                tuple(sorted(meta.produced_outputs))
            ))
        return tuple(sorted(signature_items))

    def resolve(self, registry: Any, force_refresh: bool = False) -> DependencyGraph:
        """Resolves agent classes in the registry into a validated DependencyGraph."""
        logger.info("Dependency Resolution Started")

        # 1. Extraction
        metadata_collection = MetadataExtractor.extract(registry)
        logger.info("Metadata Extracted")

        # 2. Check Cache
        current_signature = self._generate_signature(metadata_collection)
        if not force_refresh and self._cached_signature == current_signature and self._cached_graph is not None:
            logger.info("Dependency Resolution Finished (Cached)")
            return self._cached_graph

        # 3. Build Graph
        nodes, edges = DependencyGraphBuilder.build(metadata_collection)
        logger.info("Dependency Graph Built")

        # 4. Validation
        validator = DependencyGraphValidator(
            promote_orphan_warnings_to_errors=self.promote_orphan_warnings_to_errors
        )
        report = validator.validate(metadata_collection, nodes, edges)

        if not report.is_valid:
            error_msg = f"Graph validation failed: {'; '.join(report.errors)}"
            logger.error("[DependencyResolver] %s", error_msg)

            for error in report.errors:
                if "Circular dependency" in error:
                    raise CircularDependencyError(error)
                if "Duplicate producers" in error:
                    raise DuplicateProducerError(error)
                if "Missing producer" in error:
                    raise MissingDependencyError(error)
            raise InvalidDependencyGraphError(error_msg)

        logger.info("Validation Passed")

        # 5. Compute Deterministic Levels
        levels_dict: Dict[str, int] = {}

        def get_level(node_name: str) -> int:
            if node_name in levels_dict:
                return levels_dict[node_name]
            node = nodes[node_name]
            if not node.incoming:
                levels_dict[node_name] = 0
                return 0
            max_incoming_level = 0
            for parent in node.incoming:
                max_incoming_level = max(max_incoming_level, get_level(parent))
            level = 1 + max_incoming_level
            levels_dict[node_name] = level
            return level

        for name in nodes:
            get_level(name)

        levels: List[ExecutionLevel] = []
        max_level = max(levels_dict.values()) if levels_dict else -1
        for lvl in range(max_level + 1):
            level_agents = [name for name, l in levels_dict.items() if l == lvl]
            # Deterministic sorting: priority descending, name alphabetical ascending
            level_agents.sort(key=lambda name: (-nodes[name].metadata.priority, name))
            levels.append(ExecutionLevel(
                level_number=lvl,
                agents=level_agents,
                parallel=len(level_agents) > 1
            ))

        # 6. Extract statistics
        root_agents = sorted([name for name, node in nodes.items() if not node.incoming])
        leaf_agents = sorted([name for name, node in nodes.items() if not node.outgoing])
        parallelizable_groups = [lvl.agents for lvl in levels if lvl.parallel]

        stats = GraphStatistics(
            node_count=len(nodes),
            edge_count=len(edges),
            levels_count=len(levels),
            root_agents=root_agents,
            leaf_agents=leaf_agents,
            parallelizable_groups=parallelizable_groups
        )

        graph = DependencyGraph(
            nodes=nodes,
            edges=edges,
            root_agents=root_agents,
            leaf_agents=leaf_agents,
            levels=levels,
            statistics=stats
        )

        # Cache outcome
        self._cached_signature = current_signature
        self._cached_graph = graph
        logger.info("Graph Cached")
        logger.info("Dependency Resolution Finished")

        return graph
