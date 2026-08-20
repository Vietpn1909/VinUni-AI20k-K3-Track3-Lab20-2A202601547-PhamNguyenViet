"""Search client abstraction for ResearcherAgent.

Supports two modes:
- Mock mode (default): uses LLM to generate simulated search results.
- Tavily mode: if TAVILY_API_KEY is set, uses Tavily API for real web search.
"""

import json
import logging

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import SourceDocument

logger = logging.getLogger(__name__)


class SearchClient:
    """Provider-agnostic search client with mock fallback."""

    def __init__(self) -> None:
        settings = get_settings()
        self._tavily_key = settings.tavily_api_key
        self._use_tavily = bool(self._tavily_key)

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search for documents relevant to a query.

        Uses Tavily API if available, otherwise generates mock results via LLM.
        """
        if self._use_tavily:
            return self._tavily_search(query, max_results)
        return self._mock_search(query, max_results)

    def _tavily_search(self, query: str, max_results: int) -> list[SourceDocument]:
        """Real web search via Tavily API."""
        try:
            import httpx

            logger.info("Tavily search: %s (max=%d)", query, max_results)
            response = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self._tavily_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", [])[:max_results]:
                results.append(
                    SourceDocument(
                        title=item.get("title", "Untitled"),
                        url=item.get("url"),
                        snippet=item.get("content", "")[:500],
                        metadata={"score": item.get("score", 0)},
                    )
                )
            logger.info("Tavily returned %d results", len(results))
            return results

        except Exception as exc:
            logger.warning("Tavily search failed (%s), falling back to mock", exc)
            return self._mock_search(query, max_results)

    def _mock_search(self, query: str, max_results: int) -> list[SourceDocument]:
        """Generate realistic mock search results using LLM."""
        from multi_agent_research_lab.services.llm_client import LLMClient

        logger.info("Mock search (LLM-generated): %s (max=%d)", query, max_results)

        llm = LLMClient()
        system_prompt = (
            "You are a search engine simulator. Given a query, generate realistic search results. "
            "Return a JSON array of objects, each with keys: title, url, snippet. "
            "Make the results diverse, informative, and relevant. "
            f"Return exactly {max_results} results. Output ONLY valid JSON, no markdown."
        )

        try:
            response = llm.complete(system_prompt, f"Search query: {query}")
            content = response.content.strip()
            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("```", 1)[0]
            raw_results = json.loads(content)

            results = []
            for item in raw_results[:max_results]:
                results.append(
                    SourceDocument(
                        title=item.get("title", "Untitled"),
                        url=item.get("url"),
                        snippet=item.get("snippet", "")[:500],
                        metadata={"source": "mock_llm"},
                    )
                )
            logger.info("Mock search generated %d results", len(results))
            return results

        except Exception as exc:
            logger.warning("Mock search via LLM failed (%s), using static fallback", exc)
            return self._static_fallback(query, max_results)

    @staticmethod
    def _static_fallback(query: str, max_results: int) -> list[SourceDocument]:
        """Last-resort static results when everything else fails."""
        return [
            SourceDocument(
                title=f"Research Paper on {query}",
                url=f"https://arxiv.org/search/?query={query.replace(' ', '+')}",
                snippet=f"A comprehensive study exploring key aspects of {query}. "
                "This paper reviews recent advances and proposes new directions.",
                metadata={"source": "static_fallback"},
            ),
            SourceDocument(
                title=f"Survey: {query} - State of the Art",
                url=f"https://scholar.google.com/scholar?q={query.replace(' ', '+')}",
                snippet=f"This survey covers the latest developments in {query}, "
                "comparing different approaches and their trade-offs.",
                metadata={"source": "static_fallback"},
            ),
        ][:max_results]

