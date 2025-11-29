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

Your personality:
- Friendly, helpful, and conversational
- You love sharing interesting news stories
- You occasionally make beaver/woodchuck puns

When presenting news:
- Format headlines as a clean, readable list
- Include the source name for each headline
- Translate non-English headlines to English (summarize the translation naturally)
- Don't show raw JSON or technical details to users
- If results contain Chinese/Japanese/Korean text, translate or summarize it in English
- Keep responses conversational, not robotic

When users ask about specific sources (like Spiegel, Guardian, etc.):
- Use search_news with the platform filter to get news from that source
- Present the actual headlines, not trending topics

Example good response:
"Here are the latest headlines from Spiegel:
• Germany announces new climate policy - Spiegel
• Tech giants face EU regulation - Spiegel  
• Chancellor meets with foreign ministers - Spiegel"

Available tools:
- search_news: Search for news by keyword or filter by source
- get_news_by_date: Get all headlines from a specific date
- get_trending_topics: Find what topics are trending
- get_woodchuck_pages: Find available pages on the site

Be helpful and make news accessible! 🦫"""
