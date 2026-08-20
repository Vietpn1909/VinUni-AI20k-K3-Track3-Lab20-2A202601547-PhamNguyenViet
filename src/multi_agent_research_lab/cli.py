"""Command-line entrypoint for the lab starter."""

from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.errors import StudentTodoError
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging

app = typer.Typer(help="Multi-Agent Research Lab starter CLI")
console = Console()


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


def _parse_query(query: str) -> ResearchQuery:
    try:
        return ResearchQuery(query=query)
    except ValidationError as exc:
        console.print(
            Panel.fit(
                f"Invalid query: {exc.errors()[0]['msg']}",
                title="Input Error",
                style="red",
            )
        )
        raise typer.Exit(code=1) from exc


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run a minimal single-agent baseline with a real LLM call."""

    _init()
    request = _parse_query(query)
    state = ResearchState(request=request)

    from time import perf_counter

    from multi_agent_research_lab.services.llm_client import LLMClient

    llm = LLMClient()
    started = perf_counter()
    response = llm.complete(
        system_prompt=(
            "You are a research assistant. Given a query, provide a comprehensive, "
            "well-structured answer with key findings and insights. "
            "Write for technical learners. Keep your response under 500 words."
        ),
        user_prompt=request.query,
    )
    latency = perf_counter() - started

    state.final_answer = response.content
    state.add_trace_event("baseline", {
        "latency_seconds": round(latency, 2),
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "cost_usd": response.cost_usd,
    })

    console.print(Panel.fit(state.final_answer, title="Single-Agent Baseline"))
    console.print(
        f"\n[dim]⏱ Latency: {latency:.2f}s | "
        f"Tokens: {response.input_tokens}→{response.output_tokens} | "
        f"Cost: ${response.cost_usd:.6f}[/dim]"
        if response.cost_usd
        else f"\n[dim]⏱ Latency: {latency:.2f}s[/dim]"
    )


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run the multi-agent workflow skeleton."""

    _init()
    state = ResearchState(request=_parse_query(query))
    workflow = MultiAgentWorkflow()
    try:
        result = workflow.run(state)
    except StudentTodoError as exc:
        console.print(Panel.fit(str(exc), title="Expected TODO", style="yellow"))
        raise typer.Exit(code=2) from exc
    console.print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
