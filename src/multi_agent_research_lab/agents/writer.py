"""Writer agent — produces final answer from research and analysis."""

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """Produces final answer from research and analysis notes."""

    name = "writer"

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.final_answer`.

        Steps:
        1. Read research_notes, analysis_notes, and sources.
        2. Use LLM to synthesize a clear, well-structured response.
        3. Include citations referencing the source documents.
        """
        logger.info("Writer synthesizing final answer...")

        # Build source bibliography for citations
        bibliography = "\n".join(
            f"[{i + 1}] {s.title} — {s.url or 'N/A'}"
            for i, s in enumerate(state.sources)
        )

        # Determine what content is available
        research = state.research_notes or "No research notes available."
        analysis = state.analysis_notes or "No analysis notes available."

        llm = LLMClient(temperature=0.4)
        response = llm.complete(
            system_prompt=(
                "You are an expert technical writer. Given research notes, "
                "analysis, and source references, write a comprehensive, "
                "well-structured final answer.\n\n"
                "Guidelines:\n"
                f"- Write for audience: {state.request.audience}\n"
                "- Keep the response under 500 words\n"
                "- Use clear headings and structure\n"
                "- Include inline citations as [1], [2], etc.\n"
                "- End with a 'References' section listing all sources\n"
                "- Be informative, accurate, and engaging"
            ),
            user_prompt=(
                f"Query: {state.request.query}\n\n"
                f"Research Notes:\n{research}\n\n"
                f"Analysis:\n{analysis}\n\n"
                f"Available Sources:\n{bibliography}"
            ),
        )

        state.final_answer = response.content

        # --- Record result ---
        state.agent_results.append(
            AgentResult(
                agent=AgentName.WRITER,
                content=response.content[:200],
                metadata={
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                    "answer_length": len(response.content),
                },
            )
        )
        state.add_trace_event("writer_done", {
            "answer_length": len(response.content),
        })

        logger.info("Writer done: %d chars final answer", len(response.content))
        return state

