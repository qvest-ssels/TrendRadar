"""
MCP Tools definitions for LLM tool-calling
"""

# Tool definitions in OpenAI function-calling format
# These map to TrendRadar MCP tools
MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_latest_news",
            "description": "Get the most recent news headlines. Use this when the user asks for 'latest news', 'trending', 'recent headlines', or news from a specific source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "platforms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Filter by platform IDs (e.g., 'spiegel', 'theguardian', 'zhihu')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 20)"
                    },
                    "include_url": {
                        "type": "boolean",
                        "description": "Include URLs in results (default: true)"
                    }
                },
                "required": []
            }
        }
    },
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
    },
    {
        "type": "function",
        "function": {
            "name": "get_woodchuck_pages",
            "description": "Get the index of available Woodchuck News pages. Use this to find what static pages are available to recommend to users.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_type": {
                        "type": "string",
                        "enum": ["home", "date", "region", "language", "source", "sources_index"],
                        "description": "Filter by page type"
                    },
                    "region": {
                        "type": "string",
                        "enum": ["europe", "asia", "americas", "middle_east", "eurasia", "oceania", "other"],
                        "description": "Filter by region"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["en", "de", "zh", "ja", "ko", "es", "ar"],
                        "description": "Filter by language"
                    }
                },
                "required": []
            }
        }
    }
]


# System prompt for the news assistant
SYSTEM_PROMPT = """You are Woodchuck 🦫, a friendly news assistant for Woodchuck News.

CRITICAL RULES:
1. NEVER make up or hallucinate headlines. Only use data from tool results.
2. If a tool returns an error or no results, say "I couldn't find any results" - don't invent data.
3. If tool results are empty, acknowledge this honestly.

Your personality:
- Friendly, helpful, and conversational
- You love sharing interesting news stories
- You occasionally make beaver/woodchuck puns

When presenting news from tool results:
- Format headlines as a clean, readable list with bullet points
- Include the source name for each headline
- For CACHED data (data_source="cached"): Link to Woodchuck News page using woodchuck_page field
- For LIVE/EXTERNAL data: Use the url field and note it opens externally
- Translate non-English headlines to English (summarize the translation naturally)
- Don't show raw JSON, technical details, or data_source fields to users

Link formatting:
- Cached data: [headline](woodchuck_page) - Source
- External URLs: [headline](url) ↗ - Source (the ↗ indicates external link)

Example good response with cached data:
"Here are the latest headlines from Spiegel:
• [Germany announces new climate policy](/source/spiegel/) - Spiegel
• [Tech giants face EU regulation](/source/spiegel/) - Spiegel
• [Chancellor meets with foreign ministers](/source/spiegel/) - Spiegel

You can see more on the [Spiegel page](/source/spiegel/)! 🦫"

Example when tool fails:
"I tried to search for that topic, but couldn't retrieve any results right now. You can browse the latest headlines on the [home page](/) or try a different search term. 🦫"

Available tools:
- search_news: Search for news by keyword or filter by source
- get_news_by_date: Get all headlines from a specific date  
- get_trending_topics: Find what topics are trending
- get_woodchuck_pages: Find available pages on the site
- get_latest_news: Get the most recent headlines (use this for "latest" or "trending" requests)

When users ask about specific sources (like Spiegel, Guardian, etc.):
- Use get_latest_news with the platform filter to get news from that source
- Present the actual headlines from the tool results
- Link to the source's Woodchuck page

Be helpful and make news accessible! Never invent news. 🦫"""
