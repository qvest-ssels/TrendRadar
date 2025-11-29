"""
MCP Client - Communicates with TrendRadar MCP Server

This client calls the TrendRadar MCP HTTP API to execute tools.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for TrendRadar MCP Server."""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.mcp_server_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool via the HTTP API.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        logger.info(f"Calling MCP tool: {tool_name} with args: {arguments}")
        
        try:
            # Map tool names to MCP endpoints
            endpoint, method, params = self._map_tool_to_endpoint(tool_name, arguments)
            
            if method == "GET":
                response = await self.client.get(endpoint, params=params)
            else:
                response = await self.client.post(endpoint, json=params)
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"MCP tool {tool_name} returned {len(str(result))} chars")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"MCP HTTP error: {e}")
            return {"error": f"MCP server error: {e.response.status_code}"}
        except httpx.RequestError as e:
            logger.error(f"MCP request error: {e}")
            return {"error": f"Could not reach MCP server: {e}"}
        except Exception as e:
            logger.error(f"MCP call failed: {e}")
            return {"error": str(e)}
    
    def _map_tool_to_endpoint(
        self, 
        tool_name: str, 
        arguments: Dict[str, Any]
    ) -> tuple[str, str, Dict]:
        """Map tool name and arguments to MCP REST API endpoint."""
        
        # All tools are called via POST /tools/{tool_name}
        # with arguments in the request body
        return f"/tools/{tool_name}", "POST", {"arguments": arguments}


# Alternative: Direct tool execution using the data service
# This bypasses HTTP and calls TrendRadar Python code directly
class DirectMCPClient:
    """
    Direct MCP client that imports TrendRadar modules.
    Use this when running in the same environment as TrendRadar.
    """
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root
        self._tools = None
    
    def _get_tools(self):
        """Lazy-load TrendRadar tools."""
        if self._tools is None:
            try:
                import sys
                if self.project_root:
                    sys.path.insert(0, self.project_root)
                
                from mcp_server.tools.data_query import DataQueryTools
                from mcp_server.tools.search_tools import SearchTools
                from mcp_server.tools.analytics import AnalyticsTools
                
                self._tools = {
                    'data': DataQueryTools(self.project_root),
                    'search': SearchTools(self.project_root),
                    'analytics': AnalyticsTools(self.project_root)
                }
            except ImportError as e:
                logger.error(f"Could not import TrendRadar tools: {e}")
                self._tools = {}
        return self._tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool directly using TrendRadar code."""
        tools = self._get_tools()
        
        try:
            if tool_name == "search_news":
                result = tools['search'].search(
                    query=arguments.get("query", ""),
                    platforms=arguments.get("platforms"),
                    limit=arguments.get("limit", 20)
                )
                return {"results": result}
            
            elif tool_name == "get_news_by_date":
                from datetime import datetime
                date_str = arguments.get("date", "today")
                if date_str == "today":
                    target_date = datetime.now()
                else:
                    target_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                result = tools['data'].get_news_by_date(
                    platforms=arguments.get("platforms"),
                    limit=arguments.get("limit", 50)
                )
                return {"news": result}
            
            elif tool_name == "list_platforms":
                result = tools['data'].list_platforms()
                return {"platforms": result}
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Direct tool call failed: {e}")
            return {"error": str(e)}


# Singleton instances
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get or create MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client
