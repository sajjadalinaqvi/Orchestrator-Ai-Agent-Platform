import asyncio
import logging
from typing import List, Dict, Any, Optional
import requests
from urllib.parse import quote_plus
import json

logger = logging.getLogger(__name__)


class WebSearchResult:
    def __init__(self, title: str, url: str, snippet: str, source: str = "web"):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source
        }


class DuckDuckGoSearchTool:
    """Simple web search using DuckDuckGo Instant Answer API"""

    def __init__(self):
        self.base_url = "https://api.duckduckgo.com/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-Agent-Platform/1.0'
        })

    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResult]:
        """Search the web using DuckDuckGo"""
        try:
            # Use DuckDuckGo Instant Answer API
            params = {
                'q': query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }

            response = self.session.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            results = []

            # Extract instant answer if available
            if data.get('AbstractText'):
                results.append(WebSearchResult(
                    title=data.get('AbstractSource', 'DuckDuckGo'),
                    url=data.get('AbstractURL', ''),
                    snippet=data.get('AbstractText', ''),
                    source='duckduckgo_instant'
                ))

            # Extract related topics
            for topic in data.get('RelatedTopics', [])[:max_results - len(results)]:
                if isinstance(topic, dict) and 'Text' in topic:
                    results.append(WebSearchResult(
                        title=topic.get('Text', '').split(' - ')[0],
                        url=topic.get('FirstURL', ''),
                        snippet=topic.get('Text', ''),
                        source='duckduckgo_related'
                    ))

            logger.info(f"DuckDuckGo search for '{query}' returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return []


class MockWebSearchTool:
    """Mock web search for testing when no API is available"""

    def __init__(self):
        self.mock_results = {
            "ai agent": [
                WebSearchResult(
                    "What is an AI Agent?",
                    "https://example.com/ai-agent",
                    "An AI agent is a software program that can perceive its environment and take actions to achieve specific goals.",
                    "mock"
                )
            ],
            "workflow": [
                WebSearchResult(
                    "Workflow Management Systems",
                    "https://example.com/workflow",
                    "A workflow is a sequence of processes through which a piece of work passes from initiation to completion.",
                    "mock"
                )
            ],
            "default": [
                WebSearchResult(
                    "Search Results",
                    "https://example.com/search",
                    "This is a mock search result for testing purposes.",
                    "mock"
                )
            ]
        }

    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResult]:
        """Mock search that returns predefined results"""
        query_lower = query.lower()

        # Find matching mock results
        for key, results in self.mock_results.items():
            if key in query_lower:
                return results[:max_results]

        # Return default results
        return self.mock_results["default"][:max_results]


class WebSearchConnector:
    """Main web search connector that tries multiple search engines"""

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.duckduckgo = DuckDuckGoSearchTool()
        self.mock_search = MockWebSearchTool()

    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResult]:
        """Search the web using available search engines"""
        if self.use_mock:
            return await self.mock_search.search(query, max_results)

        # Try DuckDuckGo first
        results = await self.duckduckgo.search(query, max_results)

        # If no results, fall back to mock
        if not results:
            logger.warning("No results from DuckDuckGo, using mock results")
            results = await self.mock_search.search(query, max_results)

        return results

    def get_tool_info(self) -> Dict[str, Any]:
        """Get information about this tool"""
        return {
            "name": "web_search",
            "description": "Search the web for information",
            "parameters": {
                "query": "The search query string",
                "max_results": "Maximum number of results to return (default: 5)"
            },
            "example": {
                "query": "artificial intelligence",
                "max_results": 3
            }
        }
