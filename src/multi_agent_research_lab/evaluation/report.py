"""Benchmark report rendering."""

from datetime import UTC, datetime

from multi_agent_research_lab.core.schemas import BenchmarkMetrics


def render_markdown_report(metrics: list[BenchmarkMetrics]) -> str:
    """Render benchmark metrics to a rich markdown report."""

    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Benchmark Report",
        "",
        f"Generated: {now}",
        "",
        "## Results Summary",
        "",
        "| Run | Latency (s) | Cost (USD) | Quality | Citation cov. "
        "| Failure rate | Notes |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]

    for item in metrics:
        cost = (
            "" if item.estimated_cost_usd is None
            else f"{item.estimated_cost_usd:.4f}"
        )
        quality = (
            "" if item.quality_score is None
            else f"{item.quality_score:.1f}"
        )
        citation = (
            "" if item.citation_coverage is None
            else f"{item.citation_coverage:.0%}"
        )
        failure = (
            "" if item.failure_rate is None
            else f"{item.failure_rate:.0%}"
        )
        lines.append(
            f"| {item.run_name} | {item.latency_seconds:.2f} "
            f"| {cost} | {quality} "
            f"| {citation} | {failure} | {item.notes} |"
        )

    # --- Analysis section ---
    lines.extend(["", "## Analysis", ""])

    if len(metrics) >= 2:
        baseline = metrics[0]
        multi = metrics[1]

        # Latency comparison
        if baseline.latency_seconds > 0:
            ratio = multi.latency_seconds / baseline.latency_seconds
            lines.append(
                f"- **Latency**: Multi-agent is {ratio:.1f}x "
                f"{'slower' if ratio > 1 else 'faster'} than baseline."
            )

        # Quality comparison
        if baseline.quality_score is not None and multi.quality_score is not None:
            diff = multi.quality_score - baseline.quality_score
            lines.append(
                f"- **Quality**: Multi-agent scores "
                f"{'+' if diff >= 0 else ''}{diff:.1f} points "
                f"{'higher' if diff >= 0 else 'lower'} than baseline."
            )

        # Cost comparison
        if baseline.estimated_cost_usd and multi.estimated_cost_usd:
            cost_ratio = multi.estimated_cost_usd / baseline.estimated_cost_usd
            lines.append(
                f"- **Cost**: Multi-agent costs {cost_ratio:.1f}x "
                f"{'more' if cost_ratio > 1 else 'less'} than baseline."
            )

        # Citation coverage
        if multi.citation_coverage is not None:
            lines.append(
                f"- **Citation coverage**: {multi.citation_coverage:.0%} "
                f"of sources cited in multi-agent output."
            )

    # --- Failure modes section ---
    lines.extend([
        "",
        "## Failure Modes & Observations",
        "",
        "- **Infinite loops**: Mitigated by `max_iterations` guardrail "
        "in SupervisorAgent.",
        "- **Context loss**: Shared `ResearchState` ensures all agents "
        "can access prior work.",
        "- **Cost overhead**: Multi-agent makes 4+ LLM calls vs 1 for "
        "baseline — higher cost is expected.",
        "- **Quality trade-off**: Multi-agent typically scores higher on "
        "structure and citations but costs more time and tokens.",
        "",
        "## When to Use Multi-Agent",
        "",
        "- [YES] Complex research queries requiring multiple perspectives",
        "- [YES] Tasks where citation quality and source analysis matter",
        "- [NO] Simple Q&A where latency and cost are priorities",
        "- [NO] Time-critical applications with strict SLA requirements",
    ])

    return "\n".join(lines) + "\n"

