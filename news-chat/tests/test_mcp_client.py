"""Tests for MCP client functionality
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.mcp.client import MCPClient, get_mcp_client


class TestMCPClient:
    """Test MCP client."""
    
    def test_client_initialization(self):
        """Test client initializes with default URL."""
        client = MCPClient()
        assert client.base_url is not None
        assert "localhost" in client.base_url
    
    def test_client_custom_url(self):
        """Test client accepts custom URL."""
        client = MCPClient(base_url="http://custom:9999")
        assert client.base_url == "http://custom:9999"
    
    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """Test successful tool call."""
        client = MCPClient()
        
        with patch.object(client.client, 'post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "result": {"news": [{"title": "Test headline"}]}
            }
            mock_post.return_value = mock_response
            
            result = await client.call_tool("get_latest_news", {"limit": 5})
            assert result["success"] is True
            assert "news" in result["result"]
    
    @pytest.mark.asyncio
    async def test_call_tool_error_handling(self):
        """Test tool call error handling."""
        client = MCPClient()
        
        with patch.object(client.client, 'post') as mock_post:
            mock_post.side_effect = Exception("Server error")
            
            result = await client.call_tool("search_news", {"query": "test"})
            assert "error" in result


class TestMCPClientSingleton:
    """Test MCP client singleton pattern."""
    
    def test_get_mcp_client_returns_instance(self):
        """Test singleton returns MCPClient instance."""
        client = get_mcp_client()
        assert isinstance(client, MCPClient)
    
    def test_get_mcp_client_returns_same_instance(self):
        """Test singleton returns same instance."""
        client1 = get_mcp_client()
        client2 = get_mcp_client()
        assert client1 is client2
