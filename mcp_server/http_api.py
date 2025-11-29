"""
HTTP REST API wrapper for TrendRadar MCP Tools

This module provides a simple HTTP API that wraps the MCP tools,
allowing external services (like News Chat) to call them via REST.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
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
    get_woodchuck_pages,
)

# Import data layer for FTS search
from .data import get_database, get_data_store

# Import feature flags
try:
    from .utils.feature_flags import get_flags, init_flags_from_request
    FEATURE_FLAGS_AVAILABLE = True
except ImportError:
    FEATURE_FLAGS_AVAILABLE = False

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
            {"name": "get_woodchuck_pages", "description": "Get Woodchuck News page index"},
            {"name": "search_headlines_fts", "description": "Full-text search across headlines (SQLite FTS5)"},
        ]
    }


# ========== Database Search Endpoints ==========

@app.get("/search")
async def search_headlines_fts(
    q: str = Query(..., description="Search query (supports FTS5 syntax: AND, OR, NOT, phrases)"),
    platforms: Optional[str] = Query(None, description="Comma-separated platform IDs"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, description="Maximum results", ge=1, le=500)
):
    """
    Full-text search across headlines using SQLite FTS5.
    
    Query syntax examples:
    - Simple: `AI` - finds headlines containing "AI"
    - Phrase: `"artificial intelligence"` - exact phrase
    - AND: `AI AND regulation` - both terms
    - OR: `AI OR KI` - either term
    - NOT: `AI NOT china` - first but not second
    - Prefix: `tech*` - prefix matching
    """
    try:
        store = get_data_store()
        platform_list = platforms.split(',') if platforms else None
        
        results = store.search_headlines(
            query=q,
            platforms=platform_list,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        return {
            "query": q,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/headlines/latest")
async def get_latest_headlines_db(
    platforms: Optional[str] = Query(None, description="Comma-separated platform IDs"),
    limit: int = Query(50, description="Maximum results", ge=1, le=500)
):
    """Get most recent headlines from database."""
    try:
        store = get_data_store()
        platform_list = platforms.split(',') if platforms else None
        
        results = store.get_latest_headlines(
            platforms=platform_list,
            limit=limit
        )
        
        return {
            "count": len(results),
            "headlines": results
        }
    except Exception as e:
        logger.error(f"Error fetching headlines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/headlines/date/{date}")
async def get_headlines_by_date_db(
    date: str,
    platforms: Optional[str] = Query(None, description="Comma-separated platform IDs"),
    limit: int = Query(100, description="Maximum results", ge=1, le=1000)
):
    """Get headlines for a specific date from database."""
    try:
        store = get_data_store()
        platform_list = platforms.split(',') if platforms else None
        
        results = store.get_headlines_by_date(
            date=date,
            platforms=platform_list,
            limit=limit
        )
        
        return {
            "date": date,
            "count": len(results),
            "headlines": results
        }
    except Exception as e:
        logger.error(f"Error fetching headlines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/platforms/summary")
async def get_platform_summary(
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD), omit for all-time")
):
    """Get headline counts by platform."""
    try:
        store = get_data_store()
        results = store.get_platform_summary(date=date)
        
        return {
            "date": date or "all-time",
            "platforms": results
        }
    except Exception as e:
        logger.error(f"Error fetching platform summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/db/stats")
async def get_database_stats():
    """Get database statistics."""
    try:
        db = get_database()
        return db.stats()
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/urls/lookup")
async def lookup_url(
    url: str = Query(..., description="URL to look up")
):
    """Look up a URL in the registry."""
    try:
        store = get_data_store()
        result = store.lookup_url(url)
        
        if result:
            return {"found": True, "url": result}
        return {"found": False, "url": None}
    except Exception as e:
        logger.error(f"Error looking up URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: ToolRequest):
    """
    Call a specific MCP tool.
    
    Args:
        tool_name: Name of the tool to call
        request: Tool arguments
    """
    args = request.arguments
    
    # Check if paywall_bypass feature is enabled via argument
    paywall_bypass_enabled = args.get("feature_paywall_bypass") in ("1", "true", True, 1)
    
    # Also check from feature flags if available
    if not paywall_bypass_enabled and FEATURE_FLAGS_AVAILABLE:
        flags = get_flags()
        paywall_bypass_enabled = flags.is_enabled("paywall_bypass")
    
    def filter_archive_urls(result_data):
        """Remove archive_url from results if paywall_bypass is not enabled."""
        if paywall_bypass_enabled:
            return result_data
        
        # Parse if string
        if isinstance(result_data, str):
            try:
                data = json.loads(result_data)
            except json.JSONDecodeError:
                return result_data
        else:
            data = result_data
        
        # Handle dict with 'news' key
        if isinstance(data, dict) and "news" in data:
            for item in data.get("news", []):
                if isinstance(item, dict):
                    item.pop("archive_url", None)
        # Handle list of news items
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    item.pop("archive_url", None)
        
        # Return as string if input was string
        if isinstance(result_data, str):
            return json.dumps(data)
        return data
    
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
                include_url=args.get("include_url", True)  # Default to True for chat use
            )
            result = filter_archive_urls(result)
        
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
            result = filter_archive_urls(result)
        
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
            result = filter_archive_urls(result)
        
        elif tool_name == "generate_summary_report":
            result = await generate_summary_report.fn(
                date=args.get("date", "today"),
                include_sentiment=args.get("include_sentiment", True),
                max_topics=args.get("max_topics", 10)
            )
        
        elif tool_name == "get_woodchuck_pages":
            result = await get_woodchuck_pages.fn(
                page_type=args.get("page_type"),
                region=args.get("region"),
                language=args.get("language")
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
