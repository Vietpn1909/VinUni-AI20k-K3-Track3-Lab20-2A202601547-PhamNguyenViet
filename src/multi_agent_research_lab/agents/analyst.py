"""Analyst agent — turns research notes into structured insights."""

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    """Turns research notes into structured insights."""

    name = "analyst"

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.analysis_notes`.

        Steps:
        1. Read research_notes and sources from state.
        2. Use LLM to extract claims, compare viewpoints, assess evidence.
        3. Produce structured analysis notes.
        """
        logger.info("Analyst processing research notes...")

        # Build context from sources
        source_refs = "\n".join(
            f"[{i + 1}] {s.title} — {s.url or 'N/A'}"
            for i, s in enumerate(state.sources)
        )

        llm = LLMClient(temperature=0.1)
        response = llm.complete(
            system_prompt=(
                "You are a critical research analyst. Given research notes "
                "and source references, produce a structured analysis:\n\n"
                "1. **Key Claims**: List the main claims/findings.\n"
                "2. **Comparison**: Compare different viewpoints or "
                "approaches found across sources.\n"
                "3. **Evidence Quality**: Rate source reliability and flag "
                "any weak evidence or unsupported claims.\n"
                "4. **Gaps**: Note what information is missing or "
                "needs further investigation.\n"
                "5. **Synthesis**: One paragraph summarizing the "
                "overall picture.\n\n"
                "Be analytical and objective. Reference sources as [1], "
                "[2], etc."
            ),
            user_prompt=(
                f"Query: {state.request.query}\n\n"
                f"Research Notes:\n{state.research_notes}\n\n"
                f"Source References:\n{source_refs}"
            ),
        )

        state.analysis_notes = response.content

        # --- Record result ---
        state.agent_results.append(
            AgentResult(
                agent=AgentName.ANALYST,
                content=response.content[:200],
                metadata={
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event("analyst_done", {
            "analysis_length": len(response.content),
        })

        logger.info("Analyst done: %d chars of analysis", len(response.content))
        return state

