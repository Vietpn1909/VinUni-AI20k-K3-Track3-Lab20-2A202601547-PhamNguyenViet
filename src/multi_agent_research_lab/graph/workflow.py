"""LangGraph workflow for multi-agent research system.

Graph structure:
  START → supervisor → (conditional) → researcher / analyst / writer / END
  researcher → supervisor
  analyst    → supervisor
  writer     → supervisor
"""

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span

logger = logging.getLogger(__name__)

# --- Instantiate agents once ---
_supervisor = SupervisorAgent()
_researcher = ResearcherAgent()
_analyst = AnalystAgent()
_writer = WriterAgent()


# --- Node functions: convert dict ↔ ResearchState ---
def _state_from_dict(data: dict[str, Any]) -> ResearchState:
    """Reconstruct ResearchState from LangGraph state dict."""
    return ResearchState(**data)


def _state_to_dict(state: ResearchState) -> dict[str, Any]:
    """Convert ResearchState to dict for LangGraph."""
    return state.model_dump()


def supervisor_node(data: dict[str, Any]) -> dict[str, Any]:
    """Run the supervisor to decide the next route."""
    with trace_span("supervisor"):
        state = _state_from_dict(data)
        state = _supervisor.run(state)
        return _state_to_dict(state)


def researcher_node(data: dict[str, Any]) -> dict[str, Any]:
    """Run the researcher to gather sources and notes."""
    with trace_span("researcher"):
        state = _state_from_dict(data)
        state = _researcher.run(state)
        return _state_to_dict(state)


def analyst_node(data: dict[str, Any]) -> dict[str, Any]:
    """Run the analyst to produce analysis notes."""
    with trace_span("analyst"):
        state = _state_from_dict(data)
        state = _analyst.run(state)
        return _state_to_dict(state)


def writer_node(data: dict[str, Any]) -> dict[str, Any]:
    """Run the writer to produce the final answer."""
    with trace_span("writer"):
        state = _state_from_dict(data)
        state = _writer.run(state)
        return _state_to_dict(state)


def _route_after_supervisor(data: dict[str, Any]) -> str:
    """Read the last route decision from route_history and return the next node name."""
    route_history = data.get("route_history", [])
    if not route_history:
        return END

    last_route = route_history[-1]
    if last_route == "done":
        return END
    if last_route in ("researcher", "analyst", "writer"):
        return last_route

    logger.warning("Unknown route '%s', ending workflow.", last_route)
    return END


class MultiAgentWorkflow:
    """Builds and runs the multi-agent graph.

    Keep orchestration here; keep agent internals in `agents/`.
    """

    def build(self) -> StateGraph:
        """Create a LangGraph StateGraph with nodes, edges, and conditional routing."""

        graph = StateGraph(dict)

        # --- Add nodes ---
        graph.add_node("supervisor", supervisor_node)
        graph.add_node("researcher", researcher_node)
        graph.add_node("analyst", analyst_node)
        graph.add_node("writer", writer_node)

        # --- Entry point ---
        graph.set_entry_point("supervisor")

        # --- Conditional edge from supervisor ---
        graph.add_conditional_edges(
            "supervisor",
            _route_after_supervisor,
            {
                "researcher": "researcher",
                "analyst": "analyst",
                "writer": "writer",
                END: END,
            },
        )

        # --- Worker nodes always return to supervisor ---
        graph.add_edge("researcher", "supervisor")
        graph.add_edge("analyst", "supervisor")
        graph.add_edge("writer", "supervisor")

        return graph

    def run(self, state: ResearchState) -> ResearchState:
        """Execute the graph and return final state."""

        logger.info("Starting multi-agent workflow for query: %s", state.request.query[:80])

        graph = self.build()
        compiled = graph.compile()

        # Convert ResearchState to dict for LangGraph
        initial_state = _state_to_dict(state)

        # Run the graph
        with trace_span("multi_agent_workflow", {"query": state.request.query}):
            recursion_limit = get_settings().max_iterations * 3
            result = compiled.invoke(
                initial_state, config={"recursion_limit": recursion_limit}
            )

        # Convert result back to ResearchState
        final_state = _state_from_dict(result)

        logger.info(
            "Workflow complete. route_history=%s, iterations=%d",
            final_state.route_history,
            final_state.iteration,
        )

        return final_state

