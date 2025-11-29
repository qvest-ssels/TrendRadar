"""
MCP Tools definitions for LLM tool-calling
"""

# Tool definitions in OpenAI function-calling format
# These map to TrendRadar MCP tools
MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": "Search for news headlines matching a query. Use this when the user asks about specific topics, companies, or events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (keywords, company names, topics)"
                    },
                    "platforms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Filter by platform IDs (e.g., 'spiegel', 'guardian', 'xinhua')"
                    },
                    "date_range": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                            "end": {"type": "string", "description": "End date (YYYY-MM-DD)"}
                        },
                        "description": "Optional: Date range for search"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 20)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_news_by_date",
            "description": "Get news headlines for a specific date. Use this to see what news was published on a particular day.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format, or natural language like 'today', 'yesterday'"
                    },
                    "platforms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Filter by platform IDs"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 50)"
                    }
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trending_topics",
            "description": "Get trending topics and their frequency across news sources. Use this to understand what's hot right now.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date to analyze (YYYY-MM-DD or 'today')"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language filter: 'zh', 'en', 'de', etc."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of trending topics to return (default: 20)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_sentiment",
            "description": "Analyze sentiment of news coverage for a topic. Use this when user asks about how a topic is being covered or perceived.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to analyze (company, person, event)"
                    },
                    "date_range": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string"},
                            "end": {"type": "string"}
                        }
                    }
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_platforms",
            "description": "List all available news platforms/sources. Use this when user asks what sources are available.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "translate_text",
            "description": "Translate text between languages. Use when user asks for translation or to understand foreign headlines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to translate"
                    },
                    "source_language": {
                        "type": "string",
                        "description": "Source language code (e.g., 'zh', 'de', 'en')"
                    },
                    "target_language": {
                        "type": "string",
                        "description": "Target language code"
                    }
                },
                "required": ["text", "target_language"]
            }
        }
    }
]


# System prompt for the news assistant
SYSTEM_PROMPT = """You are a helpful news research assistant with access to TrendRadar, a global news aggregation system.

You can help users:
- Search for news on specific topics, companies, or events
- Find trending topics across different regions
- Analyze how topics are being covered in the media
- Translate headlines between languages
- Compare coverage across different news sources

When users ask about news, use the available tools to fetch real data. Always:
1. Use search_news for topic-specific queries
2. Use get_news_by_date for daily overviews
3. Use get_trending_topics for trend analysis
4. Cite sources when presenting news

Available regions: Europe, Eurasia, Asia-Pacific, Americas, Middle East, Oceania
Available languages: Chinese (zh), English (en), German (de), Japanese (ja), Korean (ko), Spanish (es), Arabic (ar)

Be concise but informative. When presenting headlines, include the source name."""
