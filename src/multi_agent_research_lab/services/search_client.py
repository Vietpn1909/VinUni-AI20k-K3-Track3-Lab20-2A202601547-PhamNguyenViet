"""Search client abstraction for ResearcherAgent.

Supports three modes (priority order):
1. Corpus mode: uses offline JSON corpus for real data (no API needed).
2. Tavily mode: if TAVILY_API_KEY is set, uses Tavily API for web search.
3. Mock mode (fallback): uses LLM to generate simulated search results.
"""

import json
import logging
from pathlib import Path

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import SourceDocument

logger = logging.getLogger(__name__)

# Path to the offline corpus directory
_CORPUS_DIR = (
    Path(__file__).resolve().parents[3]
    / "ai_agent_offline_research_corpus_v2"
    / "topics"
)


class SearchClient:
    """Provider-agnostic search client with offline corpus support."""

    def __init__(self) -> None:
        settings = get_settings()
        self._tavily_key = settings.tavily_api_key
        self._use_tavily = bool(self._tavily_key)
        self._corpus_loaded = False
        self._corpus_topics: list[dict] = []

        # Try to load offline corpus
        if _CORPUS_DIR.exists():
            self._load_corpus()

    def _load_corpus(self) -> None:
        """Load all topic JSON files from the offline corpus."""
        try:
            for fp in sorted(_CORPUS_DIR.glob("*.json")):
                with fp.open("r", encoding="utf-8") as f:
                    self._corpus_topics.append(json.load(f))
            self._corpus_loaded = True
            logger.info(
                "Loaded offline corpus: %d topics from %s",
                len(self._corpus_topics),
                _CORPUS_DIR,
            )
        except Exception as exc:
            logger.warning("Failed to load corpus: %s", exc)
            self._corpus_loaded = False

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search for documents relevant to a query.

        Priority: corpus -> Tavily -> mock LLM -> static fallback.
        """
        # 1. Try offline corpus first
        if self._corpus_loaded:
            results = self._corpus_search(query, max_results)
            if results:
                return results

        # 2. Try Tavily
        if self._use_tavily:
            return self._tavily_search(query, max_results)

        # 3. Fallback to mock
        return self._mock_search(query, max_results)

    def _corpus_search(
        self, query: str, max_results: int
    ) -> list[SourceDocument]:
        """Search offline corpus by keyword matching on topic + sources."""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored: list[tuple[float, SourceDocument]] = []

        for topic_data in self._corpus_topics:
            topic_info = topic_data.get("topic", {})
            # topic can be a dict with 'name' or a plain string
            if isinstance(topic_info, dict):
                topic_title = topic_info.get("name", "")
                topic_tags = topic_info.get("tags", [])
            else:
                topic_title = str(topic_info)
                topic_tags = []

            kb = topic_data.get("knowledge_base", {})

            # Score topic relevance by word overlap
            title_lower = topic_title.lower()
            title_words = set(title_lower.split())
            tags_text = " ".join(topic_tags).lower()
            overlap = len(query_words & title_words)

            # Check if any query word appears in title or tags
            keyword_hit = any(
                w in title_lower or w in tags_text
                for w in query_words
                if len(w) > 3
            )

            if overlap == 0 and not keyword_hit:
                continue

            relevance = overlap + (0.5 if keyword_hit else 0)

            # Extract source documents from this topic
            for src in kb.get("source_documents", []):
                full_text = src.get("full_text", "")
                snippet = full_text[:500] if full_text else ""
                takeaways = src.get("key_takeaways", [])
                if takeaways:
                    snippet += " | Key takeaways: " + "; ".join(
                        takeaways[:3]
                    )

                doc = SourceDocument(
                    title=src.get("title", "Untitled"),
                    url=src.get("provenance_url"),
                    snippet=snippet[:600],
                    metadata={
                        "source": "offline_corpus",
                        "document_id": src.get("document_id"),
                        "topic": topic_title,
                        "is_synthetic": src.get("is_synthetic", False),
                        "citation_label": src.get("citation_label"),
                        "weight": src.get("recommended_weight", "medium"),
                    },
                )
                scored.append((relevance, doc))

            # Also include knowledge articles
            for art in kb.get("knowledge_articles", []):
                body = art.get("body", "")
                snippet = body[:500] if body else ""

                doc = SourceDocument(
                    title=art.get("title", "Untitled"),
                    url=None,
                    snippet=snippet[:600],
                    metadata={
                        "source": "offline_corpus",
                        "article_id": art.get("article_id"),
                        "topic": topic_title,
                        "type": "knowledge_article",
                    },
                )
                scored.append((relevance * 0.8, doc))

        if not scored:
            logger.info("Corpus search: no matches for '%s'", query[:60])
            return []

        # Sort by relevance (descending) and return top results
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [doc for _, doc in scored[:max_results]]

        logger.info(
            "Corpus search: %d results for '%s' (from %d candidates)",
            len(results),
            query[:60],
            len(scored),
        )
        return results

    def _tavily_search(
        self, query: str, max_results: int
    ) -> list[SourceDocument]:
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
            logger.warning(
                "Tavily search failed (%s), falling back to mock", exc
            )
            return self._mock_search(query, max_results)

    def _mock_search(
        self, query: str, max_results: int
    ) -> list[SourceDocument]:
        """Generate realistic mock search results using LLM."""
        from multi_agent_research_lab.services.llm_client import LLMClient

        logger.info(
            "Mock search (LLM-generated): %s (max=%d)", query, max_results
        )

        llm = LLMClient()
        system_prompt = (
            "You are a search engine simulator. Given a query, "
            "generate realistic search results. "
            "Return a JSON array of objects, each with keys: "
            "title, url, snippet. "
            "Make the results diverse, informative, and relevant. "
            f"Return exactly {max_results} results. "
            "Output ONLY valid JSON, no markdown."
        )

        try:
            response = llm.complete(
                system_prompt, f"Search query: {query}"
            )
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
            logger.warning(
                "Mock search via LLM failed (%s), using static fallback",
                exc,
            )
            return self._static_fallback(query, max_results)

    @staticmethod
    def _static_fallback(
        query: str, max_results: int
    ) -> list[SourceDocument]:
        """Last-resort static results when everything else fails."""
        return [
            SourceDocument(
                title=f"Research Paper on {query}",
                url=(
                    "https://arxiv.org/search/"
                    f"?query={query.replace(' ', '+')}"
                ),
                snippet=(
                    f"A comprehensive study exploring key aspects of "
                    f"{query}. This paper reviews recent advances and "
                    "proposes new directions."
                ),
                metadata={"source": "static_fallback"},
            ),
            SourceDocument(
                title=f"Survey: {query} - State of the Art",
                url=(
                    "https://scholar.google.com/scholar"
                    f"?q={query.replace(' ', '+')}"
                ),
                snippet=(
                    f"This survey covers the latest developments in "
                    f"{query}, comparing different approaches and "
                    "their trade-offs."
                ),
                metadata={"source": "static_fallback"},
            ),
        ][:max_results]
