"""
API Routes for News Chat

Includes security measures for input validation, XSS prevention, and secret redaction.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from ..llm.client import get_llm_client
from ..mcp.client import get_mcp_client
from ..utils.security import (
    sanitize_input,
    validate_message_content,
    redact_secrets,
    detect_secrets,
)

# Add parent path for mcp_server imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
try:
    from mcp_server.utils.feature_flags import get_flags, init_flags_from_request, FeatureFlags
    from mcp_server.utils.platform_metadata import has_paywall, get_paywalled_platforms
    FEATURE_FLAGS_AVAILABLE = True
except ImportError:
    FEATURE_FLAGS_AVAILABLE = False

logger = logging.getLogger(__name__)
router = APIRouter()

# Maximum lengths for security
MAX_MESSAGE_LENGTH = 10000
MAX_MESSAGES_COUNT = 50


class ChatMessage(BaseModel):
    """A single chat message with validation."""
    role: str  # "user", "assistant", "system"
    content: str
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        """Only allow valid roles."""
        allowed_roles = {'user', 'assistant', 'system'}
        if v not in allowed_roles:
            raise ValueError(f"Invalid role: {v}. Must be one of: {allowed_roles}")
        return v
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """Sanitize and validate message content."""
        # Sanitize input
        sanitized = sanitize_input(v, max_length=MAX_MESSAGE_LENGTH)
        
        # Validate for dangerous patterns
        is_valid, error = validate_message_content(sanitized)
        if not is_valid:
            raise ValueError(error)
        
        return sanitized


class ChatRequest(BaseModel):
    """Chat request with message history."""
    messages: list[ChatMessage]
    stream: bool = True
    
    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        """Limit message count to prevent abuse."""
        if len(v) > MAX_MESSAGES_COUNT:
            raise ValueError(f"Too many messages. Maximum allowed: {MAX_MESSAGES_COUNT}")
        return v


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    message: ChatMessage
    tool_calls: Optional[list[dict]] = None


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint with tool-calling support.
    
    Streams responses when stream=True (default).
    
    Security measures applied:
    - Input sanitization and validation
    - Secret detection and redaction in responses
    - XSS prevention (handled by frontend)
    """
    llm_client = get_llm_client()
    mcp_client = get_mcp_client()
    
    # Convert to dict format for LLM (already sanitized by Pydantic)
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    # Tool executor function
    async def execute_tool(name: str, arguments: dict) -> dict:
        """Execute MCP tool and return result."""
        return await mcp_client.call_tool(name, arguments)
    
    if request.stream:
        # Stream response with secret detection
        # Note: We stream chunks directly for responsiveness, but also accumulate
        # to check for secrets. If secrets are detected mid-stream, we log a warning.
        # Full redaction happens on non-streaming responses.
        async def generate():
            full_content = ""  # Accumulate for secret detection
            async for chunk in llm_client.chat(messages, tool_executor=execute_tool):
                full_content += chunk
                
                # Quick check for obvious secret patterns in this chunk
                # Full check happens at the end
                if any(pattern in chunk.lower() for pattern in ['api_key', 'password', 'token=', 'secret']):
                    logger.debug("Potential sensitive term in chunk, will verify at end")
                
                # Stream the chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            # Final secret detection on complete response
            secrets = detect_secrets(full_content)
            if secrets:
                logger.warning(f"Potential secrets detected in streamed response: {[s[1] for s in secrets]}")
                # For streaming, we can't redact already-sent content, but we log it
                # In production, you might want to flag this response for review
            
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Content-Type-Options": "nosniff",
            }
        )
    else:
        # Non-streaming response with secret redaction
        full_response = ""
        async for chunk in llm_client.chat(messages, tool_executor=execute_tool):
            full_response += chunk
        
        # Check for and redact any secrets
        secrets = detect_secrets(full_response)
        if secrets:
            logger.warning(f"Potential secrets detected in response: {[s[1] for s in secrets]}")
            full_response = redact_secrets(full_response)
        
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


# ==================== Feature Flags Endpoints ====================

@router.get("/features")
async def get_features(request: Request):
    """
    Get current feature flags status.
    
    Feature flags can be enabled via:
    - URL params: ?feature_paywall_bypass=1
    - Cookies: feature_paywall_bypass=1
    - Environment: TRENDRADAR_FEATURE_PAYWALL_BYPASS=1
    - Config file: feature_flags.paywall_bypass=true
    """
    if not FEATURE_FLAGS_AVAILABLE:
        return {"error": "Feature flags module not available", "flags": {}}
    
    # Initialize flags from request
    params = dict(request.query_params)
    cookies = dict(request.cookies)
    flags = init_flags_from_request(params, cookies)
    
    return {
        "flags": {
            flag: {
                "enabled": flags.is_enabled(flag),
                "source": flags.get_source(flag),
            }
            for flag in flags.get_enabled_flags()
        },
        "all": flags.get_all_flags_status()
    }


@router.post("/features/{flag_name}/enable")
async def enable_feature(flag_name: str, response: Response):
    """
    Enable a feature flag via cookie.
    
    Sets a cookie that persists the feature flag for this session.
    """
    if not FEATURE_FLAGS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Feature flags not available")
    
    # Set cookie to enable feature
    response.set_cookie(
        key=f"feature_{flag_name}",
        value="1",
        max_age=86400 * 30,  # 30 days
        httponly=True,
        samesite="lax"
    )
    
    return {"status": "enabled", "flag": flag_name}


@router.post("/features/{flag_name}/disable")
async def disable_feature(flag_name: str, response: Response):
    """Disable a feature flag by removing the cookie."""
    if not FEATURE_FLAGS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Feature flags not available")
    
    response.delete_cookie(key=f"feature_{flag_name}")
    return {"status": "disabled", "flag": flag_name}


@router.get("/paywalled-sources")
async def get_paywalled_sources():
    """Get list of sources with paywalls."""
    if not FEATURE_FLAGS_AVAILABLE:
        return {"sources": []}
    
    paywalled = get_paywalled_platforms()
    return {
        "sources": [
            {
                "id": pid,
                "homepage": meta.get("homepage"),
                "paywall_type": meta.get("paywall_type", "unknown"),
                "country": meta.get("country"),
            }
            for pid, meta in paywalled.items()
        ]
    }


@router.get("/archive-url")
async def get_archive_url(url: str, request: Request):
    """
    Get archive.is URL for bypassing paywall.
    
    Only available when paywall_bypass feature is enabled.
    """
    if not FEATURE_FLAGS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Feature flags not available")
    
    # Check if feature is enabled
    params = dict(request.query_params)
    cookies = dict(request.cookies)
    flags = init_flags_from_request(params, cookies)
    
    if not flags.is_enabled("paywall_bypass"):
        raise HTTPException(
            status_code=403, 
            detail="Paywall bypass feature not enabled. Use ?feature_paywall_bypass=1 or enable via /features/paywall_bypass/enable"
        )
    
    return {
        "original_url": url,
        "archive_url": FeatureFlags.get_archive_url(url),
        "archive_newest": FeatureFlags.get_archive_newest_url(url),
        "archive_search": FeatureFlags.get_archive_search_url(url),
    }
