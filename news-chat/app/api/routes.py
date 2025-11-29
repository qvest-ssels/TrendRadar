"""
API Routes for News Chat
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..llm.client import get_llm_client
from ..mcp.client import get_mcp_client

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user", "assistant", "system"
    content: str


class ChatRequest(BaseModel):
    """Chat request with message history."""
    messages: list[ChatMessage]
    stream: bool = True


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    message: ChatMessage
    tool_calls: Optional[list[dict]] = None


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint with tool-calling support.
    
    Streams responses when stream=True (default).
    """
    llm_client = get_llm_client()
    mcp_client = get_mcp_client()
    
    # Convert to dict format for LLM
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    # Tool executor function
    async def execute_tool(name: str, arguments: dict) -> dict:
        """Execute MCP tool and return result."""
        return await mcp_client.call_tool(name, arguments)
    
    if request.stream:
        # Stream response
        async def generate():
            async for chunk in llm_client.chat(messages, tool_executor=execute_tool):
                # Send as SSE
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    else:
        # Non-streaming response
        full_response = ""
        async for chunk in llm_client.chat(messages, tool_executor=execute_tool):
            full_response += chunk
        
        return ChatResponse(
            message=ChatMessage(role="assistant", content=full_response)
        )


@router.get("/models")
async def list_models():
    """List available Ollama models."""
    llm_client = get_llm_client()
    try:
        models = await llm_client.ollama_client.list()
        return {
            "models": [
                {
                    "name": m.get("name", ""),
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", "")
                }
                for m in models.get("models", [])
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama not available: {e}")


@router.get("/tools")
async def list_tools():
    """List available MCP tools."""
    from ..llm.tools import MCP_TOOLS
    return {
        "tools": [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"]
            }
            for t in MCP_TOOLS
        ]
    }


@router.get("/status")
async def status():
    """Check connection status to Ollama and MCP."""
    llm_client = get_llm_client()
    mcp_client = get_mcp_client()
    
    ollama_ok = await llm_client.check_connection()
    
    # Check MCP server
    mcp_ok = False
    try:
        response = await mcp_client.client.get("/health")
        mcp_ok = response.status_code == 200
    except Exception:
        pass
    
    return {
        "ollama": {
            "connected": ollama_ok,
            "model": llm_client.model
        },
        "mcp": {
            "connected": mcp_ok,
            "url": mcp_client.base_url
        }
    }
