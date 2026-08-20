"""Benchmark framework for single-agent vs multi-agent comparison."""

import logging
import re
from collections.abc import Callable
from time import perf_counter

from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState

logger = logging.getLogger(__name__)

Runner = Callable[[str], ResearchState]


def _count_citations(text: str) -> int:
    """Count citation references like [1], [2], etc. in text."""
    return len(set(re.findall(r"\[\d+\]", text)))


def _estimate_total_cost(state: ResearchState) -> float | None:
    """Sum up cost_usd from all agent results and trace events."""
    total = 0.0
    found_any = False

    for result in state.agent_results:
        cost = result.metadata.get("cost_usd")
        if cost is not None:
            total += cost
            found_any = True

    for event in state.trace:
        cost = event.get("payload", {}).get("cost_usd")
        if cost is not None:
            total += cost
            found_any = True

    return total if found_any else None


def _compute_citation_coverage(state: ResearchState) -> float | None:
    """Ratio of cited sources vs total sources."""
    if not state.sources or not state.final_answer:
        return None

    total_sources = len(state.sources)
    cited = _count_citations(state.final_answer)
    return min(cited / total_sources, 1.0) if total_sources > 0 else None


def _assess_quality(state: ResearchState) -> float | None:
    """Quick quality score (0-10) based on heuristics.

    Checks: has answer, length, has citations, has structure.
    For a more robust score, use LLM-as-judge (expensive).
    """
    if not state.final_answer:
        return 0.0

    answer = state.final_answer
    score = 0.0

    # Has content (0-3 points)
    length = len(answer)
    if length > 100:
        score += 1.0
    if length > 300:
        score += 1.0
    if length > 500:
        score += 1.0

    # Has citations (0-2 points)
    citations = _count_citations(answer)
    if citations >= 1:
        score += 1.0
    if citations >= 3:
        score += 1.0

    # Has structure - headings or bullet points (0-2 points)
    if "#" in answer or "**" in answer:
        score += 1.0
    if "- " in answer or "* " in answer or "\n1." in answer:
        score += 1.0

    # Based on research notes (0-2 points)
    if state.research_notes:
        score += 1.0
    if state.analysis_notes:
        score += 1.0

    # Has references section (0-1 point)
    if "reference" in answer.lower() or "source" in answer.lower():
        score += 1.0

    return min(score, 10.0)


def run_benchmark(
    run_name: str, query: str, runner: Runner
) -> tuple[ResearchState, BenchmarkMetrics]:
    """Run a query through a runner and measure all metrics."""

    logger.info("Benchmark '%s' starting: %s", run_name, query[:60])

    # --- Run with timing ---
    failure = False
    started = perf_counter()
    try:
        state = runner(query)
    except Exception as exc:
        logger.error("Benchmark '%s' failed: %s", run_name, exc)
        failure = True
        state = ResearchState(
            request={"query": query},  # type: ignore[arg-type]
            errors=[str(exc)],
        )
    latency = perf_counter() - started

    # --- Compute metrics ---
    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=round(latency, 2),
        estimated_cost_usd=_estimate_total_cost(state),
        quality_score=_assess_quality(state),
        citation_coverage=_compute_citation_coverage(state),
        failure_rate=1.0 if failure else 0.0,
        notes=f"route_history={state.route_history}" if state.route_history else "",
    )

    logger.info(
        "Benchmark '%s' done: latency=%.2fs quality=%.1f cost=$%s",
        run_name,
        metrics.latency_seconds,
        metrics.quality_score or 0,
        f"{metrics.estimated_cost_usd:.6f}" if metrics.estimated_cost_usd else "N/A",
    )

    return state, metrics

