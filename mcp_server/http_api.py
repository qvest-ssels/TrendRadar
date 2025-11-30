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
    deep_search,
    get_wikipedia_context,
    search_wikipedia,
    search_huggingface_models,
    search_huggingface_datasets,
    get_ml_papers,
    search_arxiv,
    search_github_repos,
    expert_research,
    search_youtube,
    get_youtube_transcript,
    search_udemy,
    search_conferences,
    search_newsletters,
    get_popular_newsletters,
    search_movies,
    get_movie_details,
    search_person,
    get_person_filmography,
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
            {"name": "deep_search", "description": "Deep search - combines local cache with live site search"},
            {"name": "get_wikipedia_context", "description": "Get Wikipedia background info for a topic"},
            {"name": "search_wikipedia", "description": "Search Wikipedia for articles"},
            {"name": "search_huggingface_models", "description": "🧑‍🔬 Ask an Expert: Search HuggingFace for ML models"},
            {"name": "search_huggingface_datasets", "description": "🧑‍🔬 Ask an Expert: Search HuggingFace for datasets"},
            {"name": "get_ml_papers", "description": "🧑‍🔬 Ask an Expert: Get latest ML/AI research papers"},
            {"name": "search_arxiv", "description": "🧑‍🔬 Ask an Expert: Search arXiv for academic papers"},
            {"name": "search_github_repos", "description": "🧑‍🔬 Ask an Expert: Search GitHub for repositories"},
            {"name": "expert_research", "description": "🧑‍🔬 Ask an Expert: Comprehensive research (papers + repos + models)"},
            {"name": "search_youtube", "description": "🎬 Search YouTube for tutorials and educational videos"},
            {"name": "get_youtube_transcript", "description": "🎬 Get transcript from a YouTube video"},
            {"name": "search_udemy", "description": "📚 Search Udemy for online courses"},
            {"name": "search_conferences", "description": "🎤 Search for tech conferences"},
            {"name": "search_newsletters", "description": "📰 Search for newsletters by topic"},
            {"name": "get_popular_newsletters", "description": "⭐ Get popular/recommended newsletters"},
            {"name": "search_movies", "description": "🎬 Search IMDB for movies and TV shows"},
            {"name": "get_movie_details", "description": "🎥 Get detailed movie/show information"},
            {"name": "search_person", "description": "👤 Search for actors, directors, etc."},
            {"name": "get_person_filmography", "description": "🎭 Get filmography for a person"},
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


@app.get("/cache/stats")
async def get_cache_stats():
    """
    Get API cache statistics.
    
    Returns stats for all caches (github, arxiv, huggingface) including:
    - size: current number of entries
    - hits/misses: cache hit/miss counts
    - hit_rate: percentage of cache hits
    """
    try:
        from .utils.cache import get_all_cache_stats
        return {
            "success": True,
            "caches": get_all_cache_stats()
        }
    except ImportError:
        return {
            "success": False,
            "error": "Cache module not available"
        }
    except Exception as e:
        logger.error(f"Error fetching cache stats: {e}")
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
                date_query=args.get("date", args.get("date_query", "today")),
                platforms=args.get("platforms", args.get("platform")),
                limit=args.get("limit", 50),
                include_url=args.get("include_url", True)
            )
            result = filter_archive_urls(result)
        
        elif tool_name == "analyze_topic_trend":
            # Support both 'days' shorthand and 'date_range' object
            date_range = args.get("date_range")
            if not date_range and args.get("days"):
                # Convert days to date_range
                from datetime import datetime, timedelta
                end = datetime.now()
                start = end - timedelta(days=int(args.get("days")))
                date_range = {
                    "start": start.strftime("%Y-%m-%d"),
                    "end": end.strftime("%Y-%m-%d")
                }
            
            result = await analyze_topic_trend.fn(
                topic=args.get("topic", ""),
                analysis_type=args.get("analysis_type", "trend"),
                date_range=date_range,
                granularity=args.get("granularity", "day")
            )
        
        elif tool_name == "analyze_sentiment":
            # Support both 'headlines' list and topic-based analysis
            headlines = args.get("headlines")
            if headlines:
                # Direct sentiment analysis of provided headlines
                # Return a simple structure for AI to interpret
                result = json.dumps({
                    "success": True,
                    "mode": "direct_headlines",
                    "headlines": headlines,
                    "count": len(headlines),
                    "note": "Headlines provided for sentiment analysis. Analyze these for positive/negative/neutral sentiment."
                }, ensure_ascii=False)
            else:
                result = await analyze_sentiment.fn(
                    topic=args.get("topic"),
                    date_range=args.get("date_range"),
                    platforms=args.get("platforms"),
                    limit=args.get("limit", 50),
                    sort_by_weight=args.get("sort_by_weight", True),
                    include_url=args.get("include_url", False)
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
            # Support both old (date) and new (report_type/date_range) APIs
            report_type = args.get("report_type", "daily")
            date_range = args.get("date_range")
            
            # If date is provided, convert to date_range format
            if not date_range and args.get("date"):
                date_range = {"start": args.get("date"), "end": args.get("date")}
            
            result = await generate_summary_report.fn(
                report_type=report_type,
                date_range=date_range
            )
        
        elif tool_name == "get_woodchuck_pages":
            result = await get_woodchuck_pages.fn(
                page_type=args.get("page_type"),
                region=args.get("region"),
                language=args.get("language")
            )
        
        elif tool_name == "search_headlines_fts":
            # FTS5 full-text search via data store
            store = get_data_store()
            query = args.get("query", args.get("q", ""))
            platforms = args.get("platforms")
            if isinstance(platforms, str):
                platforms = platforms.split(",")
            
            results = store.search_headlines(
                query=query,
                platforms=platforms,
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
                limit=args.get("limit", 50)
            )
            
            # Convert datetime objects to strings for JSON serialization
            serializable_results = []
            for item in results:
                clean_item = {}
                for k, v in item.items():
                    if hasattr(v, 'isoformat'):  # datetime objects
                        clean_item[k] = v.isoformat()
                    else:
                        clean_item[k] = v
                serializable_results.append(clean_item)
            
            result = json.dumps({
                "query": query,
                "count": len(serializable_results),
                "results": serializable_results
            }, ensure_ascii=False)
        
        elif tool_name == "deep_search":
            result = await deep_search.fn(
                query=args.get("query", ""),
                platforms=args.get("platforms"),
                language=args.get("language"),
                mode=args.get("mode", "both"),
                max_results=args.get("max_results", 50),
                date_range=args.get("date_range"),
                include_url=args.get("include_url", True)
            )
            result = filter_archive_urls(result)
        
        elif tool_name == "get_wikipedia_context":
            result = await get_wikipedia_context.fn(
                topic=args.get("topic", ""),
                language=args.get("language", "en"),
                include_related=args.get("include_related", False)
            )
        
        elif tool_name == "search_wikipedia":
            result = await search_wikipedia.fn(
                query=args.get("query", ""),
                language=args.get("language", "en"),
                limit=args.get("limit", 5)
            )
        
        # Ask an Expert - HuggingFace tools
        elif tool_name == "search_huggingface_models":
            result = await search_huggingface_models.fn(
                query=args.get("query", ""),
                task=args.get("task"),
                sort=args.get("sort", "downloads"),
                limit=args.get("limit", 10)
            )
        
        elif tool_name == "search_huggingface_datasets":
            result = await search_huggingface_datasets.fn(
                query=args.get("query", ""),
                sort=args.get("sort", "downloads"),
                limit=args.get("limit", 10)
            )
        
        elif tool_name == "get_ml_papers":
            result = await get_ml_papers.fn(
                query=args.get("query"),
                limit=args.get("limit", 10)
            )
        
        # Ask an Expert - arXiv papers
        elif tool_name == "search_arxiv":
            result = await search_arxiv.fn(
                query=args.get("query", ""),
                category=args.get("category"),
                max_results=args.get("max_results", 10)
            )
        
        # Ask an Expert - GitHub repos
        elif tool_name == "search_github_repos":
            result = await search_github_repos.fn(
                query=args.get("query", ""),
                language=args.get("language"),
                sort=args.get("sort", "stars"),
                limit=args.get("limit", 10),
                min_stars=args.get("min_stars")
            )
        
        # Ask an Expert - Combined research
        elif tool_name == "expert_research":
            result = await expert_research.fn(
                query=args.get("query", ""),
                include_papers=args.get("include_papers", True),
                include_repos=args.get("include_repos", True),
                include_models=args.get("include_models", True),
                include_datasets=args.get("include_datasets", False),
                max_results_per_source=args.get("max_results_per_source", 5)
            )
        
        # YouTube tools
        elif tool_name == "search_youtube":
            result = await search_youtube.fn(
                query=args.get("query", ""),
                limit=args.get("limit", 5)
            )
        
        elif tool_name == "get_youtube_transcript":
            result = await get_youtube_transcript.fn(
                video_id=args.get("video_id", ""),
                max_length=args.get("max_length", 10000)
            )
        
        # Learning & Education tools
        elif tool_name == "search_udemy":
            result = await search_udemy.fn(
                query=args.get("query", ""),
                level=args.get("level"),
                min_rating=args.get("min_rating", 0.0),
                limit=args.get("limit", 10),
                free_only=args.get("free_only", False)
            )
        
        elif tool_name == "search_conferences":
            result = await search_conferences.fn(
                topic=args.get("topic"),
                year=args.get("year"),
                country=args.get("country"),
                city=args.get("city"),
                limit=args.get("limit", 20),
                include_past=args.get("include_past", False)
            )
        
        elif tool_name == "search_newsletters":
            result = await search_newsletters.fn(
                query=args.get("query", ""),
                category=args.get("category"),
                limit=args.get("limit", 10)
            )
        
        elif tool_name == "get_popular_newsletters":
            result = await get_popular_newsletters.fn(
                category=args.get("category"),
                limit=args.get("limit", 10)
            )
        
        # Entertainment tools
        elif tool_name == "search_movies":
            result = await search_movies.fn(
                query=args.get("query", ""),
                content_type=args.get("content_type"),
                year=args.get("year"),
                limit=args.get("limit", 10)
            )
        
        elif tool_name == "get_movie_details":
            result = await get_movie_details.fn(
                imdb_id=args.get("imdb_id"),
                title=args.get("title"),
                year=args.get("year")
            )
        
        elif tool_name == "search_person":
            result = await search_person.fn(
                name=args.get("name"),
                include_wikipedia=args.get("include_wikipedia", True)
            )
        
        elif tool_name == "get_person_filmography":
            result = await get_person_filmography.fn(
                imdb_id=args.get("imdb_id"),
                limit=args.get("limit", 20)
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
