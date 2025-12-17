import asyncio
import logging
from typing import Dict, Any, List, Optional
import sys
import os

# Add packages to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'packages'))

from connectors import WebSearchConnector
from guardrails import ContentGuardrails

logger = logging.getLogger(__name__)


class ToolsRegistry:
    """Registry for all available tools and connectors"""

    def __init__(self):
        self.tools = {}
        self.guardrails = ContentGuardrails()
        self._initialize_tools()

    def _initialize_tools(self):
        """Initialize all available tools"""
        # Web Search Tool
        self.tools['web_search'] = {
            'connector': WebSearchConnector(use_mock=True),  # Use mock for now
            'info': {
                'name': 'web_search',
                'description': 'Search the web for information',
                'parameters': ['query', 'max_results'],
                'category': 'information'
            }
        }

        # Document Search Tool (uses RAG system)
        self.tools['document_search'] = {
            'connector': None,  # Will be set by RAG system
            'info': {
                'name': 'document_search',
                'description': 'Search through uploaded documents',
                'parameters': ['query', 'limit'],
                'category': 'information'
            }
        }

        logger.info(f"Initialized {len(self.tools)} tools")

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any], tenant_id: str = "default") -> Dict[
        str, Any]:
        """Execute a tool with given parameters"""

        # Check if tool exists
        if tool_name not in self.tools:
            return {
                'success': False,
                'error': f'Tool {tool_name} not found',
                'available_tools': list(self.tools.keys())
            }

        # Check tool access permissions
        if not self.guardrails.check_tool_access(tool_name, tenant_id):
            return {
                'success': False,
                'error': f'Access denied for tool {tool_name}',
                'tenant_id': tenant_id
            }

        try:
            tool = self.tools[tool_name]
            connector = tool['connector']

            if tool_name == 'web_search':
                return await self._execute_web_search(connector, parameters)
            elif tool_name == 'document_search':
                return await self._execute_document_search(connector, parameters)
            else:
                return {
                    'success': False,
                    'error': f'Tool {tool_name} execution not implemented'
                }

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'tool_name': tool_name
            }

    async def _execute_web_search(self, connector: WebSearchConnector, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute web search"""
        query = parameters.get('query', '')
        max_results = parameters.get('max_results', 5)

        if not query:
            return {
                'success': False,
                'error': 'Query parameter is required for web search'
            }

        # Apply input guardrails
        guardrail_result = self.guardrails.process_input(query)
        if guardrail_result.result.value == 'blocked':
            return {
                'success': False,
                'error': 'Query blocked by content filter',
                'violations': guardrail_result.violations
            }

        # Execute search
        results = await connector.search(guardrail_result.content, max_results)

        # Apply output guardrails to results
        filtered_results = []
        for result in results:
            output_guardrail = self.guardrails.process_output(result.snippet)
            if output_guardrail.result.value != 'blocked':
                filtered_results.append({
                    'title': result.title,
                    'url': result.url,
                    'snippet': output_guardrail.content,
                    'source': result.source
                })

        return {
            'success': True,
            'results': filtered_results,
            'query': guardrail_result.content,
            'total_results': len(filtered_results)
        }

    async def _execute_document_search(self, connector, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute document search (placeholder)"""
        return {
            'success': False,
            'error': 'Document search not yet implemented in tools registry'
        }

    def get_available_tools(self, tenant_id: str = "default") -> List[Dict[str, Any]]:
        """Get list of available tools for a tenant"""
        available_tools = []

        for tool_name, tool_data in self.tools.items():
            if self.guardrails.check_tool_access(tool_name, tenant_id):
                available_tools.append(tool_data['info'])

        return available_tools

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific tool"""
        if tool_name in self.tools:
            return self.tools[tool_name]['info']
        return None

    def register_tool(self, tool_name: str, connector: Any, info: Dict[str, Any]):
        """Register a new tool"""
        self.tools[tool_name] = {
            'connector': connector,
            'info': info
        }
        logger.info(f"Registered new tool: {tool_name}")

    def update_guardrails_config(self, config: Dict[str, Any]):
        """Update guardrails configuration"""
        self.guardrails.update_config(config)

    def get_guardrails_stats(self) -> Dict[str, Any]:
        """Get guardrails statistics"""
        return self.guardrails.get_stats()