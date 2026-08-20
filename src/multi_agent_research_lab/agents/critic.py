"""Critic agent — optional fact-checking and safety review."""

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class CriticAgent(BaseAgent):
    """Optional fact-checking and safety-review agent."""

    name = "critic"

    def run(self, state: ResearchState) -> ResearchState:
        """Validate final answer and append findings.

        Checks:
        1. Citation coverage — are claims backed by sources?
        2. Factual consistency — does the answer align with research?
        3. Hallucination risk — any claims not in the source material?
        """
        if not state.final_answer:
            logger.warning("Critic: no final_answer to review.")
            return state

        logger.info("Critic reviewing final answer...")

        source_refs = "\n".join(
            f"[{i + 1}] {s.title}: {s.snippet[:100]}"
            for i, s in enumerate(state.sources)
        )

        llm = LLMClient(temperature=0.0)
        response = llm.complete(
            system_prompt=(
                "You are a fact-checker reviewing a research answer. "
                "Evaluate the following:\n\n"
                "1. **Citation Check**: Are all major claims supported "
                "by the cited sources?\n"
                "2. **Consistency**: Does the answer accurately reflect "
                "the research notes?\n"
                "3. **Hallucination Risk**: Flag any statements that "
                "appear unsupported by the provided sources.\n"
                "4. **Overall Rating**: Rate 1-5 (1=poor, 5=excellent)."
                "\n\nBe concise and specific."
            ),
            user_prompt=(
                f"Answer to review:\n{state.final_answer}\n\n"
                f"Research notes:\n{state.research_notes or 'N/A'}\n\n"
                f"Sources:\n{source_refs}"
            ),
        )

        # Append critique to errors list for visibility
        state.errors.append(f"Critic review: {response.content[:500]}")

        state.agent_results.append(
            AgentResult(
                agent=AgentName.CRITIC,
                content=response.content[:200],
                metadata={
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event("critic_done", {
            "review_length": len(response.content),
        })

        logger.info("Critic done: %d chars review", len(response.content))
        return state

