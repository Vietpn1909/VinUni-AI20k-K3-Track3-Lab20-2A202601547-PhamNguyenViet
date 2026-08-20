"""Researcher agent — gathers sources and creates research notes."""

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes."""

    name = "researcher"

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.sources` and `state.research_notes`.

        Steps:
        1. Search for relevant sources using SearchClient.
        2. Summarize all source snippets into research notes via LLM.
        3. Record results in state for downstream agents.
        """
        query = state.request.query
        max_sources = state.request.max_sources
        logger.info("Researcher searching: '%s' (max=%d)", query, max_sources)

        # --- Step 1: Gather sources ---
        search = SearchClient()
        sources = search.search(query, max_results=max_sources)
        state.sources = sources
        logger.info("Found %d sources", len(sources))

        # --- Step 2: Summarize into research notes via LLM ---
        source_text = "\n\n".join(
            f"[{i + 1}] {s.title}\n    URL: {s.url or 'N/A'}\n    {s.snippet}"
            for i, s in enumerate(sources)
        )

        llm = LLMClient()
        response = llm.complete(
            system_prompt=(
                "You are a research assistant. Given a collection of search "
                "results, create structured research notes. Include:\n"
                "- Key findings from each source\n"
                "- Important facts and data points\n"
                "- Source references using [1], [2], etc.\n"
                "Be concise but thorough. Write in bullet points."
            ),
            user_prompt=(
                f"Research query: {query}\n\n"
                f"Sources found:\n{source_text}"
            ),
        )

        state.research_notes = response.content

        # --- Record result ---
        state.agent_results.append(
            AgentResult(
                agent=AgentName.RESEARCHER,
                content=response.content[:200],
                metadata={
                    "sources_count": len(sources),
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event("researcher_done", {
            "sources_count": len(sources),
            "notes_length": len(response.content),
        })

        logger.info(
            "Researcher done: %d sources, %d chars of notes",
            len(sources),
            len(response.content),
        )
        return state

