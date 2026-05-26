"""
Pipeline — DAG-based orchestrator for market intelligence.

Replaces implicit cron dependencies with an explicit directed acyclic graph.
Each node is a function: MarketState -> MarketState.

Usage:
    # Programmatic
    pipeline = Pipeline("morning_brief")
    state = MarketState(trade_date="2026-05-26")
    state = pipeline.run(state)

    # CLI
    python -m src pipeline --name morning_brief --explain
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.state import MarketState


# ── Pipeline Registry ────────────────────────────────────────────────────────
# Pipeline definitions: name -> list of (node_name, dependencies, fn_name)
# fn_name maps to an actual callable via PIPELINE_FUNCTIONS

PIPELINE_REGISTRY: Dict[str, List[Dict[str, Any]]] = {}


def register_pipeline(name: str, nodes: List[Dict[str, Any]]):
    """Register a pipeline definition."""
    PIPELINE_REGISTRY[name] = nodes


def register_function(name: str, fn: Callable[[MarketState], MarketState]):
    """Register a pipeline function (node callable)."""
    PIPELINE_FUNCTIONS[name] = fn


PIPELINE_FUNCTIONS: Dict[str, Callable[[MarketState], MarketState]] = {}


# ── DAG Pipeline Runner ─────────────────────────────────────────────────────

class PipelineNode:
    """A single computation step in the pipeline."""

    def __init__(self, name: str, dependencies: List[str], fn: Callable[[MarketState], MarketState], description: str = ""):
        self.name = name
        self.dependencies = dependencies
        self.fn = fn
        self.description = description
        self.elapsed: Optional[float] = None
        self.status: str = "pending"  # pending / running / success / failed / skipped
        self.error: Optional[str] = None

    def execute(self, state: MarketState) -> MarketState:
        """Execute this node."""
        self.status = "running"
        start = time.time()
        try:
            result = self.fn(state)
            self.elapsed = time.time() - start
            self.status = "success"
            return result
        except Exception as e:
            self.elapsed = time.time() - start
            self.status = "failed"
            self.error = f"{type(e).__name__}: {e}"
            state.missing_sources.append(f"{self.name}: {self.error}")
            return state

    def __repr__(self):
        return f"PipelineNode({self.name}, deps={self.dependencies}, status={self.status})"


class Pipeline:
    """
    DAG-based pipeline runner with topological sort.

    Args:
        name: Pipeline name (must be registered in PIPELINE_REGISTRY)
        strict: If True, raise on node failure. If False, continue with degraded state.
        timeout: Max seconds for entire pipeline.
    """

    def __init__(self, name: str, strict: bool = False, timeout: Optional[int] = None):
        self.name = name
        self.strict = strict
        self.timeout = timeout or 300
        self.nodes: Dict[str, PipelineNode] = {}
        self.graph: Dict[str, List[str]] = defaultdict(list)  # adjacency list
        self.in_degree: Dict[str, int] = defaultdict(int)
        self.execution_order: List[str] = []
        self.total_elapsed: float = 0

        self._build_graph()

    def _build_graph(self):
        """Build the DAG from the registered pipeline definition."""
        if self.name not in PIPELINE_REGISTRY:
            raise ValueError(f"Pipeline '{self.name}' not registered. Available: {list(PIPELINE_REGISTRY.keys())}")

        for node_def in PIPELINE_REGISTRY[self.name]:
            node_name = node_def["name"]
            deps = node_def.get("dependencies", [])
            fn_name = node_def["fn"]
            description = node_def.get("description", "")

            fn = PIPELINE_FUNCTIONS.get(fn_name)
            if fn is None:
                raise ValueError(f"Pipeline function '{fn_name}' not registered for node '{node_name}'")

            node = PipelineNode(node_name, deps, fn, description)
            self.nodes[node_name] = node

            for dep in deps:
                self.graph[dep].append(node_name)
                self.in_degree[node_name] += 1

    def _topological_sort(self) -> List[str]:
        """Kahn's algorithm for topological ordering."""
        queue = deque()
        for node_name in self.nodes:
            if self.in_degree[node_name] == 0:
                queue.append(node_name)

        order = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for neighbor in self.graph[current]:
                self.in_degree[neighbor] -= 1
                if self.in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.nodes):
            cycle_nodes = set(self.nodes.keys()) - set(order)
            raise ValueError(f"Circular dependency detected in pipeline '{self.name}': {cycle_nodes}")

        return order

    def run(self, state: MarketState) -> MarketState:
        """Execute the full pipeline, returning updated MarketState."""
        start = time.time()
        self.execution_order = self._topological_sort()

        completed: Set[str] = set()
        failed: Set[str] = set()

        for node_name in self.execution_order:
            # Check timeout
            if time.time() - start > self.timeout:
                self._skip_remaining(node_name, self.execution_order[self.execution_order.index(node_name):])
                break

            node = self.nodes[node_name]

            # Check if all dependencies succeeded
            deps_failed = any(d in failed for d in node.dependencies)
            if deps_failed and node.dependencies:
                node.status = "skipped"
                node.error = f"Dependency failed: {[d for d in node.dependencies if d in failed]}"
                failed.add(node_name)
                print(f"  ⏭️  {node_name}: skipped (dependency failed)")
                continue

            print(f"  ▶️  {node_name}")
            state = node.execute(state)
            elapsed_str = f"{node.elapsed:.1f}s" if node.elapsed else "?"

            if node.status == "success":
                completed.add(node_name)
                print(f"  ✅ {node_name} ({elapsed_str})")
            elif node.status == "failed":
                failed.add(node_name)
                print(f"  ❌ {node_name} ({elapsed_str}) — {node.error}")
                if self.strict:
                    raise RuntimeError(f"Pipeline node '{node_name}' failed: {node.error}")

        self.total_elapsed = time.time() - start
        self._print_summary(completed, failed)
        return state

    def _skip_remaining(self, current: str, remaining: List[str]):
        """Mark all remaining nodes as skipped due to timeout."""
        for node_name in remaining:
            self.nodes[node_name].status = "skipped"
            self.nodes[node_name].error = "Pipeline timeout"
            print(f"  ⏭️  {node_name}: skipped (timeout)")

    def _print_summary(self, completed: Set[str], failed: Set[str]):
        """Print pipeline execution summary."""
        total = len(self.nodes)
        print(f"\n{'='*50}")
        print(f"Pipeline '{self.name}' completed in {self.total_elapsed:.1f}s")
        print(f"  ✅ {len(completed)} succeeded | ❌ {len(failed)} failed | ⏭️ {total - len(completed) - len(failed)} skipped")
        if self.nodes:
            for node_name in self.execution_order:
                node = self.nodes[node_name]
                if node.elapsed:
                    print(f"    {node_name}: {node.elapsed:.1f}s [{node.status}]")
        print(f"{'='*50}")

    def explain(self) -> str:
        """Generate a Mermaid diagram of the pipeline."""
        lines = [f"```mermaid", f"graph TD"]

        for node_name in self.execution_order if self.execution_order else self.nodes:
            node = self.nodes[node_name]
            deps = node.dependencies
            if deps:
                for dep in deps:
                    lines.append(f"    {dep} --> {node_name}")
            else:
                lines.append(f"    {node_name}")

        lines.append("```")
        return "\n".join(lines)

    def get_status(self) -> Dict[str, Any]:
        """Execution status dict for logging."""
        return {
            "pipeline": self.name,
            "total_elapsed": round(self.total_elapsed, 1),
            "nodes": {
                name: {
                    "status": node.status,
                    "elapsed": round(node.elapsed, 1) if node.elapsed else None,
                    "error": node.error,
                }
                for name, node in self.nodes.items()
            },
        }


# ── CLI Entry Point ─────────────────────────────────────────────────────────

def main_cli():
    parser = argparse.ArgumentParser(description="Market Intelligence Pipeline Runner")
    parser.add_argument("pipeline", nargs="?", default="morning_brief", help="Pipeline name")
    parser.add_argument("--explain", action="store_true", help="Show Mermaid DAG diagram")
    parser.add_argument("--list", action="store_true", help="List available pipelines")
    parser.add_argument("--strict", action="store_true", help="Fail fast on node errors")
    args = parser.parse_args()

    if args.list:
        print("Available pipelines:")
        for name, nodes in PIPELINE_REGISTRY.items():
            print(f"  {name} — {len(nodes)} nodes")
        return

    if args.pipeline not in PIPELINE_REGISTRY:
        print(f"Error: Pipeline '{args.pipeline}' not found. Available: {list(PIPELINE_REGISTRY.keys())}")
        sys.exit(1)

    # Build and show pipeline
    pipeline = Pipeline(args.pipeline, strict=args.strict)
    pipeline._topological_sort()  # Pre-compute order for explain

    if args.explain:
        print(pipeline.explain())
        print()

    # Execute
    from src.state import MarketState
    from datetime import datetime
    state = MarketState(trade_date=datetime.now().strftime("%Y-%m-%d"))
    print(f"Running pipeline '{args.pipeline}' for {state.trade_date}...")
    state = pipeline.run(state)
    print(f"\nState summary: {state.summary()}")
