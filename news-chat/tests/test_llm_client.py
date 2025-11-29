"""Tests for LLM client functionality
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.llm.client import LLMClient, get_llm_client
from app.llm.tools import MCP_TOOLS, SYSTEM_PROMPT


class TestLLMTools:
    """Test LLM tool definitions."""
    
    def test_mcp_tools_defined(self):
        """Test MCP tools are defined."""
        assert MCP_TOOLS is not None
        assert len(MCP_TOOLS) > 0
    
    def test_tools_have_required_fields(self):
        """Test each tool has required fields."""
        for tool in MCP_TOOLS:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
    
    def test_system_prompt_defined(self):
        """Test system prompt is defined."""
        assert SYSTEM_PROMPT is not None
        assert len(SYSTEM_PROMPT) > 0
        assert "news" in SYSTEM_PROMPT.lower()


class TestLLMClient:
    """Test LLM client."""
    
    def test_client_initialization(self):
        """Test client initializes correctly."""
        client = LLMClient()
        assert client.model is not None
        assert client.tools == MCP_TOOLS
    
    @pytest.mark.asyncio
    async def test_check_connection_mocked(self):
        """Test connection check with mocked Ollama."""
        client = LLMClient()
        
        with patch.object(client.ollama_client, 'list') as mock_list:
            mock_list.return_value = {"models": []}
            result = await client.check_connection()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_check_connection_failure(self):
        """Test connection check handles failure."""
        client = LLMClient()
        
        with patch.object(client.ollama_client, 'list') as mock_list:
            mock_list.side_effect = Exception("Connection refused")
            result = await client.check_connection()
            assert result is False


class TestLLMClientSingleton:
    """Test LLM client singleton pattern."""
    
    def test_get_llm_client_returns_instance(self):
        """Test singleton returns LLMClient instance."""
        client = get_llm_client()
        assert isinstance(client, LLMClient)
    
    def test_get_llm_client_returns_same_instance(self):
        """Test singleton returns same instance."""
        client1 = get_llm_client()
        client2 = get_llm_client()
        assert client1 is client2
