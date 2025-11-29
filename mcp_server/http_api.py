"""
HTTP REST API wrapper for TrendRadar MCP Tools

This module provides a simple HTTP API that wraps the MCP tools,
allowing external services (like News Chat) to call them via REST.
"""

import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import MCP tool functions directly from server
from .server import (
    resolve_date_range,
    get_latest_news,
    get_trending_topics,
    get_news_by_date,
    analyze_topic_trend,
    analyze_sentiment,
    search_news,
    generate_summary_report,
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="TrendRadar MCP REST API",
    description="HTTP wrapper for TrendRadar MCP tools",
    version="1.0.0"
)

# Add CORS for News Chat
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ToolRequest(BaseModel):
    """Request body for tool calls."""
    arguments: Dict[str, Any] = {}


class ToolResponse(BaseModel):
    """Response from tool execution."""
    success: bool
    result: Any
    error: Optional[str] = None


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "trendradar-mcp-rest"}


@app.get("/tools")
async def list_tools():
    """List available tools."""
    return {
        "tools": [
            {"name": "resolve_date_range", "description": "Parse natural language date expressions"},
            {"name": "get_latest_news", "description": "Get latest news headlines"},
            {"name": "get_trending_topics", "description": "Get trending topics"},
            {"name": "get_news_by_date", "description": "Get headlines for a specific date"},
            {"name": "analyze_topic_trend", "description": "Analyze trend for a topic"},
            {"name": "analyze_sentiment", "description": "Analyze sentiment of headlines"},
            {"name": "search_news", "description": "Search news headlines by keyword"},
            {"name": "generate_summary_report", "description": "Generate a summary report"},
        ]
    }


@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: ToolRequest):
    """
    Call a specific MCP tool.
    
    Args:
        tool_name: Name of the tool to call
        request: Tool arguments
    """
    args = request.arguments
    
    try:
        # Access the underlying function via .fn attribute of FunctionTool
        if tool_name == "resolve_date_range":
            result = await resolve_date_range.fn(
                expression=args.get("expression", "today")
            )
        
        elif tool_name == "get_latest_news":
            result = await get_latest_news.fn(
                platforms=args.get("platforms"),
                limit=args.get("limit", 10),
                include_url=args.get("include_url", False)
            )
        
        elif tool_name == "get_trending_topics":
            result = await get_trending_topics.fn(
                top_n=args.get("top_n", 10),
                mode=args.get("mode", "current")
            )
        
        elif tool_name == "get_news_by_date":
            result = await get_news_by_date.fn(
                date=args.get("date", "today"),
                platform=args.get("platform"),
                limit=args.get("limit", 50)
            )
        
        elif tool_name == "analyze_topic_trend":
            result = await analyze_topic_trend.fn(
                topic=args.get("topic", ""),
                date_range=args.get("date_range")
            )
        
        elif tool_name == "analyze_sentiment":
            result = await analyze_sentiment.fn(
                topic=args.get("topic"),
                date_range=args.get("date_range"),
                platforms=args.get("platforms")
            )
        
        elif tool_name == "search_news":
            result = await search_news.fn(
                query=args.get("query", ""),
                date_range=args.get("date_range"),
                platforms=args.get("platforms"),
                limit=args.get("limit", 20)
            )
        
        elif tool_name == "generate_summary_report":
            result = await generate_summary_report.fn(
                date=args.get("date", "today"),
                include_sentiment=args.get("include_sentiment", True),
                max_topics=args.get("max_topics", 10)
            )
        
        else:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
        # Parse JSON result
        return ToolResponse(success=True, result=json.loads(result))
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        raise HTTPException(status_code=500, detail="Invalid JSON response from tool")
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return ToolResponse(success=False, result=None, error=str(e))


def create_app():
    """Factory function to create the FastAPI app."""
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3334)
