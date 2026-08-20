"""Tests for SupervisorAgent routing policy.

Replaces the original skeleton guard test since SupervisorAgent is now implemented.
"""

from multi_agent_research_lab.agents import SupervisorAgent
from multi_agent_research_lab.core.schemas import ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState


def _make_state(**kwargs) -> ResearchState:
    """Helper to create a ResearchState with defaults."""
    return ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"), **kwargs
    )


def test_supervisor_routes_to_researcher_when_no_sources() -> None:
    state = _make_state()
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "researcher"


def test_supervisor_routes_to_analyst_when_sources_present() -> None:
    state = _make_state(
        sources=[SourceDocument(title="Paper 1", snippet="Some content")],
        research_notes="Found relevant sources.",
    )
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "analyst"


def test_supervisor_routes_to_writer_when_analysis_done() -> None:
    state = _make_state(
        sources=[SourceDocument(title="Paper 1", snippet="Some content")],
        research_notes="Found relevant sources.",
        analysis_notes="Analysis of findings.",
    )
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "writer"


def test_supervisor_routes_to_done_when_all_complete() -> None:
    state = _make_state(
        sources=[SourceDocument(title="Paper 1", snippet="Some content")],
        research_notes="Found relevant sources.",
        analysis_notes="Analysis of findings.",
        final_answer="Here is the complete answer.",
    )
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "done"


def test_supervisor_enforces_max_iterations() -> None:
    state = _make_state(iteration=10)  # exceeds default max of 6
    result = SupervisorAgent().run(state)
    # Should force stop or rush to writer
    assert result.route_history[-1] in ("done", "writer")

