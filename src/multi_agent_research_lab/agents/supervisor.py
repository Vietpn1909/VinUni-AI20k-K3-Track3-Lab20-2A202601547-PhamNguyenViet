"""Supervisor / router agent.

Routing policy:
  1. No sources yet        → route to 'researcher'
  2. No analysis yet       → route to 'analyst'
  3. No final answer yet   → route to 'writer'
  4. Everything filled     → route to 'done'

Guardrails:
  - Enforces max_iterations from config.
  - Falls back to 'writer' if approaching limit without final_answer.
"""

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.state import ResearchState

logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """Decides which worker should run next and when to stop."""

    name = "supervisor"

    def run(self, state: ResearchState) -> ResearchState:
        """Update `state.route_history` with the next route.

        Inspects request, current notes, and missing fields to choose
        one of: researcher, analyst, writer, done.
        """
        settings = get_settings()
        max_iter = settings.max_iterations

        # --- Guardrail: max iterations reached ---
        if state.iteration >= max_iter:
            logger.warning(
                "Max iterations reached (%d/%d). Forcing stop.", state.iteration, max_iter
            )
            route = "done" if state.final_answer else "writer"
            state.record_route(route)
            state.add_trace_event("supervisor_route", {
                "route": route,
                "reason": "max_iterations_reached",
                "iteration": state.iteration,
            })
            return state

        # --- Routing decision based on state completeness ---
        if not state.sources and not state.research_notes:
            route = "researcher"
            reason = "no sources or research notes yet"
        elif not state.analysis_notes:
            route = "analyst"
            reason = "sources present but no analysis notes"
        elif not state.final_answer:
            route = "writer"
            reason = "analysis done but no final answer"
        else:
            route = "done"
            reason = "all fields populated"

        # --- Near-limit fallback: if close to max and no final_answer, rush to writer ---
        if route != "done" and state.iteration >= max_iter - 1 and not state.final_answer:
            route = "writer"
            reason = (
                f"approaching max_iterations ({state.iteration + 1}/{max_iter}), rushing to writer"
            )
            logger.warning("Near iteration limit — forcing route to writer.")

        logger.info(
            "Supervisor [iter=%d/%d] route='%s' reason='%s'",
            state.iteration + 1,
            max_iter,
            route,
            reason,
        )

        state.record_route(route)
        state.add_trace_event("supervisor_route", {
            "route": route,
            "reason": reason,
            "iteration": state.iteration,
        })

        return state

