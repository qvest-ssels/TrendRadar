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
            "name": "deep_search",
            "description": "Deep search for news on a specific topic. Combines local headlines with live search on news sites. Use for researching specific people, companies, events, or topics. Best for: 'news about Elon Musk', 'latest Tesla news', 'climate change coverage'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - person name, company, event, or topic"
                    },
                    "platforms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Specific platforms to search (e.g., ['theguardian', 'spiegel'])"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["en", "de", "fr", "zh"],
                        "description": "Optional: Filter by language"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["headlines", "site_search", "both"],
                        "description": "Search mode: 'headlines' (fast, local), 'site_search' (thorough, live), 'both' (recommended)"
                    }
                },
                "required": ["query"]
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
            "name": "get_wikipedia_context",
            "description": "Get Wikipedia background info for a topic. Use when users ask 'Who is X?', 'What is Y?', or need context about a person, company, or event mentioned in news.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to look up (person, company, event, etc.)"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["en", "de", "fr", "es", "zh", "ja", "ru", "pt", "ar", "ko"],
                        "description": "Wikipedia language (default: en)"
                    },
                    "include_related": {
                        "type": "boolean",
                        "description": "Include related topics (default: false)"
                    }
                },
                "required": ["topic"]
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
    },
    # Ask an Expert - HuggingFace tools
    {
        "type": "function",
        "function": {
            "name": "search_huggingface_models",
            "description": "🧑‍🔬 Ask an Expert: Search HuggingFace for ML models. Use for questions about best models, LLMs, ML tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'code generation', 'llama', 'sentiment')"
                    },
                    "task": {
                        "type": "string",
                        "enum": ["text-generation", "text-classification", "translation", "summarization", "conversational", "text-to-image", "automatic-speech-recognition", "feature-extraction"],
                        "description": "Filter by task type (optional)"
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["downloads", "likes", "created", "modified"],
                        "description": "Sort by (default: downloads)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_huggingface_datasets",
            "description": "🧑‍🔬 Ask an Expert: Search HuggingFace for ML datasets. Use for questions about training data, benchmarks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'sentiment', 'code', 'medical')"
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["downloads", "likes", "created", "modified"],
                        "description": "Sort by (default: downloads)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ml_papers",
            "description": "🧑‍🔬 Ask an Expert: Get latest ML/AI research papers from HuggingFace Daily Papers or search by topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (optional - if empty, returns latest papers)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    }
                },
                "required": []
            }
        }
    },
    # Ask an Expert - arXiv papers
    {
        "type": "function",
        "function": {
            "name": "search_arxiv",
            "description": "🧑‍🔬 Ask an Expert: Search arXiv for academic research papers. Best for scientific/technical research.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'large language models', 'quantum computing', 'neural networks')"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["cs.AI", "cs.CL", "cs.LG", "cs.CV", "cs.NE", "stat.ML", "cs.IR", "cs.SE"],
                        "description": "arXiv category (optional). cs.AI=AI, cs.CL=NLP, cs.LG=ML, cs.CV=Computer Vision, cs.NE=Neural, stat.ML=Statistics ML"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    # Ask an Expert - GitHub repos
    {
        "type": "function",
        "function": {
            "name": "search_github_repos",
            "description": "🧑‍🔬 Ask an Expert: Search GitHub for open source repositories and libraries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'web scraping', 'machine learning', 'react components')"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript", "typescript", "java", "go", "rust", "c", "cpp", "csharp", "ruby", "php", "swift", "kotlin"],
                        "description": "Filter by programming language (optional)"
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["stars", "forks", "updated", "best-match"],
                        "description": "Sort by (default: stars)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    },
                    "min_stars": {
                        "type": "integer",
                        "description": "Minimum star count (optional)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    # Ask an Expert - Combined research
    {
        "type": "function",
        "function": {
            "name": "expert_research",
            "description": "🧑‍🔬 Ask an Expert: PREFERRED for broad technical questions. Combines arXiv papers + GitHub repos + HuggingFace models. IMPORTANT: Response contains 'papers' array with 'title', 'authors', 'url', 'pdf_url' - you MUST show authors!",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Research topic (e.g., 'RAG retrieval augmented generation', 'vision transformers', 'sentiment analysis')"
                    },
                    "include_papers": {
                        "type": "boolean",
                        "description": "Include arXiv papers (default: true)"
                    },
                    "include_repos": {
                        "type": "boolean",
                        "description": "Include GitHub repos (default: true)"
                    },
                    "include_models": {
                        "type": "boolean",
                        "description": "Include HuggingFace models (default: true)"
                    },
                    "include_datasets": {
                        "type": "boolean",
                        "description": "Include HuggingFace datasets (default: false)"
                    },
                    "max_results_per_source": {
                        "type": "integer",
                        "description": "Max results per source (default: 5)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    # Ask an Expert - YouTube
    {
        "type": "function",
        "function": {
            "name": "search_youtube",
            "description": "🎬 Search YouTube for tutorials, educational videos, and tech content. Great for learning how-to guides.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'python tutorial', 'machine learning explained')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 5)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_youtube_transcript",
            "description": "🎬 Get the transcript/captions from a YouTube video. Useful for summarizing video content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {
                        "type": "string",
                        "description": "YouTube video ID (the part after v= in the URL)"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Max transcript length in characters (default: 10000)"
                    }
                },
                "required": ["video_id"]
            }
        }
    },
    # Ask an Expert - Learning & Education
    {
        "type": "function",
        "function": {
            "name": "search_udemy",
            "description": "📚 Search Udemy for online courses. Find courses on any topic with ratings and reviews.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'python programming', 'data science')"
                    },
                    "level": {
                        "type": "string",
                        "enum": ["beginner", "intermediate", "expert", "all"],
                        "description": "Course difficulty level (optional)"
                    },
                    "min_rating": {
                        "type": "number",
                        "description": "Minimum rating 0-5 (default: 0)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    },
                    "free_only": {
                        "type": "boolean",
                        "description": "Only show free courses (default: false)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_conferences",
            "description": "🎤 Search for tech conferences and events. Find upcoming conferences by topic, location, or date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Conference topic (e.g., 'AI', 'DevOps', 'JavaScript')"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Conference year (default: current year)"
                    },
                    "country": {
                        "type": "string",
                        "description": "Country code (e.g., 'DE', 'US', 'UK')"
                    },
                    "city": {
                        "type": "string",
                        "description": "City name"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 20)"
                    },
                    "include_past": {
                        "type": "boolean",
                        "description": "Include past conferences (default: false)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_newsletters",
            "description": "📰 Search for newsletters by topic. Find curated newsletters for tech, business, and more.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'AI', 'startup', 'programming')"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["tech", "ai", "business", "design", "marketing", "finance", "startup", "programming"],
                        "description": "Newsletter category (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_popular_newsletters",
            "description": "⭐ Get popular/recommended newsletters by category. Curated list of quality newsletters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["tech", "ai", "business", "design", "marketing", "finance", "startup", "programming"],
                        "description": "Newsletter category (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    }
                },
                "required": []
            }
        }
    },
    # Ask an Expert - Entertainment (IMDB)
    {
        "type": "function",
        "function": {
            "name": "search_movies",
            "description": "🎬 Search IMDB for movies and TV shows. Find information about films, series, and documentaries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (movie title, TV show name)"
                    },
                    "content_type": {
                        "type": "string",
                        "enum": ["movie", "series", "episode"],
                        "description": "Content type filter (optional)"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Release year (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_movie_details",
            "description": "🎥 Get detailed information about a movie or TV show. Includes cast, plot, ratings, awards.",
            "parameters": {
                "type": "object",
                "properties": {
                    "imdb_id": {
                        "type": "string",
                        "description": "IMDB ID (e.g., 'tt0111161')"
                    },
                    "title": {
                        "type": "string",
                        "description": "Movie/show title (if no IMDB ID)"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Release year (helps with title search)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_person",
            "description": "👤 Search for actors, directors, and other film industry people. Includes Wikipedia cross-reference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Person's name (e.g., 'Tom Hanks', 'Christopher Nolan')"
                    },
                    "include_wikipedia": {
                        "type": "boolean",
                        "description": "Include Wikipedia bio (default: true)"
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_person_filmography",
            "description": "🎭 Get filmography for an actor or director. Lists their movies and TV appearances.",
            "parameters": {
                "type": "object",
                "properties": {
                    "imdb_id": {
                        "type": "string",
                        "description": "IMDB person ID (e.g., 'nm0000158')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 20)"
                    }
                },
                "required": ["imdb_id"]
            }
        }
    },
    # Ask an Expert - People Search
    {
        "type": "function",
        "function": {
            "name": "search_politician",
            "description": "🏛️ Search for politicians, especially German Bundestag members. Uses Wikipedia and official sources.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Politician's name (e.g., 'Olaf Scholz', 'Angela Merkel')"
                    },
                    "party": {
                        "type": "string",
                        "description": "Party filter (e.g., 'SPD', 'CDU', 'Grüne')"
                    },
                    "country": {
                        "type": "string",
                        "description": "Country code (default: 'de' for Germany)"
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_people",
            "description": "🔍 General people search via Wikipedia. Find information about notable people.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Person's name"
                    },
                    "person_type": {
                        "type": "string",
                        "enum": ["politician", "scientist", "artist", "athlete", "business", "general"],
                        "description": "Type of person to search for (optional)"
                    },
                    "language": {
                        "type": "string",
                        "description": "Wikipedia language (default: 'de')"
                    }
                },
                "required": ["name"]
            }
        }
    },
    # Business Intelligence - North Data Company Lookups
    {
        "type": "function",
        "function": {
            "name": "search_company",
            "description": "🏢 Search European Companies (via North Data). Find companies across 22 European countries (DE, AT, CH, GB, FR, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Company name or keyword (e.g., 'Siemens', 'startup AI Berlin')"
                    },
                    "countries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Country codes to search (e.g., ['DE', 'AT']). Empty for all countries."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "terminated", "liquidation"],
                        "description": "Filter by company status"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_details",
            "description": "🏢 Get detailed company information (via North Data). Returns financials, executives, shareholders, and events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Company name (e.g., 'Siemens AG')"
                    },
                    "address": {
                        "type": "string",
                        "description": "City for disambiguation (e.g., 'München')"
                    },
                    "register_id": {
                        "type": "string",
                        "description": "German register ID (e.g., 'HRB 12345')"
                    },
                    "register_city": {
                        "type": "string",
                        "description": "Court city (e.g., 'München')"
                    },
                    "include_financials": {
                        "type": "boolean",
                        "description": "Include revenue, profit, employees (default: true)"
                    },
                    "include_relations": {
                        "type": "boolean",
                        "description": "Include executives and shareholders (default: true)"
                    },
                    "include_events": {
                        "type": "boolean",
                        "description": "Include company events (default: false)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_executive",
            "description": "👔 Search business executives (via North Data). Find company directors, managers, and shareholders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {
                        "type": "string",
                        "description": "First name(s)"
                    },
                    "last_name": {
                        "type": "string",
                        "description": "Last name (required)"
                    },
                    "address": {
                        "type": "string",
                        "description": "City for disambiguation"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    }
                },
                "required": ["last_name"]
            }
        }
    },
    # System tools
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "📊 Get system status and health information. Shows service status, data statistics, and cache info.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


# System prompt for the news assistant
SYSTEM_PROMPT = """You are Woodchuck 🦫, a friendly news assistant for Woodchuck News.

LANGUAGE RULE - CRITICAL:
- ALWAYS respond in the SAME LANGUAGE as the user's question
- If user writes in German → respond in German
- If user writes in English → respond in English
- If user writes in French → respond in French
- NEVER mix languages in your response
- NEVER switch to Chinese or any other language unless the user asked in that language

META QUESTIONS - About yourself and your capabilities:
When users ask "what can you do?", "which tools do you have?", "help", or similar:
→ Do NOT call any tool
→ Explain your capabilities directly:

"I'm Woodchuck 🦫, your AI news assistant! Here's what I can help you with:

📰 **News & Headlines**
- Latest news from 30+ global sources
- Search news by topic, company, or person
- Deep search across news sites

📚 **Research & Learning**
- Wikipedia background info on any topic
- arXiv academic papers
- GitHub repositories
- HuggingFace ML models & datasets
- YouTube tutorials & transcripts
- Udemy courses
- Tech conferences
- Newsletters

🏢 **Business Intelligence** (via North Data)
- Search European companies (22 countries)
- Company details, financials, executives
- Business executive lookups

🎬 **Entertainment**
- Movie & TV show info (IMDB)
- Actor/director filmographies

👤 **People**
- Politician info (German Bundestag)
- Celebrity & public figure lookups

🌐 **Translation**
- Translate text between languages
- Translate news headlines

⚙️ **System**
- Check system status (get_system_status)

Just ask me anything! 🦫"

CRITICAL RULES - YOU MUST FOLLOW THESE:
1. YOU MUST CALL A TOOL to get news data. NEVER generate fake headlines.
2. NEVER make up URLs - only use URLs returned by tools.
3. If you don't have real data from a tool, say "I need to fetch the data" and call a tool.
4. If a tool returns an error or no results, say "I couldn't find any results" - don't invent data.
5. Every headline you show MUST come from tool results - NO EXCEPTIONS.

SYSTEM STATUS:
- When user asks "system status", "check status", "how are you doing" → call get_system_status
- Present the results in a friendly way, showing service health and data statistics

MANDATORY: When user asks for news, headlines, or any information:
→ FIRST call get_latest_news or search_news to get REAL data
→ THEN present only the headlines from the tool response
→ NEVER skip the tool call and generate your own headlines

Your personality:
- Friendly, helpful, and conversational
- You love sharing interesting news stories
- You occasionally make beaver/woodchuck puns

IMPORTANT - Tool Selection Guidelines:
- For "latest news", "recent headlines", "what's happening": Use get_latest_news (NOT search_news)
- For "technology news", "tech headlines", etc.: Use get_latest_news first (with heise or slashdot for tech), then filter/highlight tech stories
- For specific topics like "AI news", "climate news": Use search_news with the exact keyword
- For specific people (Elon Musk, Trump, etc.): Use deep_search - it searches across sites
- For specific companies (Tesla, Apple, etc.): Use deep_search - more thorough than search_news
- For in-depth research on any topic: Use deep_search with mode="both"
- For "Who is X?", "What is Y?", background info: Use get_wikipedia_context
- search_news only finds headlines containing the EXACT keyword - for better results use deep_search

DEEP SEARCH (deep_search tool):
- Best for: researching specific people, companies, events
- Searches both local headlines AND live news sites
- Example: "news about Elon Musk" → deep_search(query="Elon Musk", mode="both")
- Example: "Tesla news in German" → deep_search(query="Tesla", language="de")
- Supports: theguardian, spiegel, aljazeera, heise, lemonde, straitstimes, timesofindia

WIKIPEDIA CONTEXT (get_wikipedia_context tool):
- Use for: "Who is X?", "What is Y?", "Tell me about Z", background info
- Provides Wikipedia summary, description, and link
- Supports multiple languages (en, de, fr, zh, ja, etc.)
- Example: "Who is Elon Musk?" → get_wikipedia_context(topic="Elon Musk")
- Example: "Was ist Tesla?" → get_wikipedia_context(topic="Tesla, Inc.", language="de")
- Great for providing context alongside news results
- IMPORTANT: When presenting Wikipedia results:
  1. If "thumbnail_image_url" exists, show the image: ![Title](thumbnail_image_url)
  2. Present the extract/summary text
  3. End with article link using "url" field: [Read more on Wikipedia](url)
  4. NEVER use thumbnail_image_url as a clickable link - it's just an image!
  5. **ALWAYS offer to search for related news**: After showing Wikipedia info, ask:
     "Would you like me to search for recent news about [topic]?" 🦫
     This helps users discover current events related to the topic they looked up.

🧑‍🔬 ASK AN EXPERT - Technical Research Tools:

**PREFERRED: expert_research** - Use for broad technical questions!
This combines arXiv papers + GitHub repos + HuggingFace models in one call:
- "How do I build a RAG system?" → expert_research(query="RAG retrieval augmented generation")
- "State of the art in image generation" → expert_research(query="diffusion models image generation")
- "Best approaches for sentiment analysis" → expert_research(query="sentiment analysis NLP")
- Returns: papers (research), repos (implementations), models (pre-trained)

**Individual tools** - Use for specific narrow queries:

- search_huggingface_models: Find ML models for specific tasks
  - "Best LLM for code generation" → search_huggingface_models(query="code generation", task="text-generation")

- search_huggingface_datasets: Find training/benchmark datasets
  - "Datasets for sentiment analysis" → search_huggingface_datasets(query="sentiment")

- get_ml_papers: Latest AI/ML research papers
  - "Latest AI research" → get_ml_papers()

- search_arxiv: Academic papers with university affiliations
  - "NLP papers about BERT" → search_arxiv(query="BERT", category="cs.CL")

- search_github_repos: Open source projects and libraries
  - "Python web scraping libraries" → search_github_repos(query="web scraping", language="python")

When presenting expert_research or search_arxiv results:
**CRITICAL - Extract data from the tool response!**

The tool response contains structured data. You MUST extract and display:

📄 **For arXiv Papers** - Extract from response and show:
- **title** → Show as clickable link: [title](url)
- **authors** → ALWAYS show! The response contains an "authors" array - display first 3-5 names
- **affiliations** → Show if present in response
- **url** → Make title clickable
- **pdf_url** → Add PDF link: [📄 PDF](pdf_url)
- **published** → Show date

Example output format:
"1. **[AR-RAG: Autoregressive Retrieval Augmentation](https://arxiv.org/abs/2506.06962)** [📄 PDF](https://arxiv.org/pdf/2506.06962.pdf)
   👤 Authors: Jingyuan Qi, Zhiyang Xu, Qifan Wang
   📅 Published: June 2025"

⚠️ DO NOT say "Authors: [Not specified]" - the authors ARE in the response data!

📦 **For GitHub Repos** - Extract and show:
- **name** → Show as clickable link: [name](url)
- **stargazers_count** → Show as "⭐ X stars"
- **language** → Show programming language
- **description** → Show short description

🤗 **For HuggingFace Models** - Extract and show:
- **id** → Show as clickable link
- **downloads** → Show download count
- **task** → Show task type

📦 **For GitHub Repos** - ALWAYS show:
- Name as clickable link: [repo-name](url)
- Stars, language, description
- If marked "likely_implements_paper" → highlight as implementation!

🤗 **For HuggingFace Models** - ALWAYS show:
- Model name as clickable link: [model-name](url)
- Downloads count, task type

NEVER just list names without links - always make them clickable!

🎬 YOUTUBE & VIDEO LEARNING:

- search_youtube: Find video tutorials and educational content
  - "Python tutorial for beginners" → search_youtube(query="python tutorial beginner")
  - "How to build a RAG system" → search_youtube(query="RAG retrieval augmented generation tutorial")

- get_youtube_transcript: Get video transcripts for summarization
  - "Summarize this video" → get_youtube_transcript(video_id="dQw4w9WgXcQ")

📚 COURSES & LEARNING:

- search_udemy: Find online courses on any topic
  - "Python courses for beginners" → search_udemy(query="python", level="beginner")
  - "Free data science courses" → search_udemy(query="data science", free_only=true)

- search_conferences: Find tech conferences and events
  - "AI conferences in Germany" → search_conferences(topic="AI", country="DE")
  - "JavaScript conferences 2025" → search_conferences(topic="JavaScript", year=2025)

- search_newsletters: Find curated newsletters
  - "AI newsletters" → search_newsletters(query="AI", category="ai")
  - "Startup newsletters" → get_popular_newsletters(category="startup")

🎬 MOVIES & TV (IMDB):

- search_movies: Find movies and TV shows
  - "Search for Inception" → search_movies(query="Inception")
  - "Find sci-fi movies from 2024" → search_movies(query="science fiction", year=2024)

- get_movie_details: Get detailed info (cast, plot, ratings)
  - "Tell me about The Matrix" → get_movie_details(title="The Matrix")

- search_person: Find actors, directors with Wikipedia bio
  - "Who is Christopher Nolan?" → search_person(name="Christopher Nolan")

- get_person_filmography: List someone's movies/shows
  - "Tom Hanks movies" → get_person_filmography(imdb_id="nm0000158")

🏛️ PEOPLE & POLITICIANS:

- search_politician: Search German/international politicians
  - "Who is Olaf Scholz?" → search_politician(name="Olaf Scholz")
  - "SPD politicians" → search_politician(name="", party="SPD")

- search_people: General Wikipedia people search
  - "Who is Elon Musk?" → search_people(name="Elon Musk")

**IMPORTANT**: After showing person/politician info, ALWAYS offer to search for news:
  - "Would you like me to search for recent news about [person name]?" 🦫
  - For politicians, this is especially useful to find their latest statements or activities
  - For celebrities/actors, this can find recent interviews or projects

🏢 BUSINESS INTELLIGENCE (North Data - European Companies):

- search_company: Search companies across 22 European countries
  - "Find Siemens" → search_company(query="Siemens", countries=["DE"])
  - "Startups in Berlin" → search_company(query="startup Berlin", status="active")
  - "Search DACH companies" → search_company(query="tech", countries=["DE", "AT", "CH"])

- get_company_details: Get detailed company info (financials, executives, shareholders)
  - "Details about SAP" → get_company_details(name="SAP SE", address="Walldorf")
  - "Volkswagen executives" → get_company_details(name="Volkswagen AG", include_relations=true)

- search_executive: Find business executives and their company roles
  - "Find CEO Müller" → search_executive(last_name="Müller")
  - "Find Tim Cook" → search_executive(first_name="Tim", last_name="Cook")

**Company format**: Show company info cleanly:
  - Name (Legal Form) - City, Country
  - Status: Active/Terminated
  - Link to North Data profile when available

AVAILABLE PLATFORMS (use only these):
Tech/Science: heise, slashdot
German: spiegel, tagesspiegel, heise
English: theguardian, guardianau, aljazeera, straitstimes, japantimes, timesofindia, timesofisrael, dailymaverick, wsj
French: lemonde
Spanish: elpais, elpais_mexico
Portuguese: folha
Russian: moscowtimes
Chinese: zhihu, weibo, baidu, toutiao, bilibili-hot-search, thepaper, douyin, ifeng, tieba, cls-hot, wallstreetcn-hot

Note: wsj (Wall Street Journal) has a paywall - show 🔒 archive links when available.

DO NOT use platforms that don't exist (like techcrunch, forbes, engadget, bbc, etc.)

When presenting news from tool results:
- Format headlines as a clean, readable list with bullet points
- Include the source name for each headline
- Use the 'url' field to link to the actual article
- If only 'woodchuck_page' is present: Link to the Woodchuck News archive page
- Translate non-English headlines to English (summarize the translation naturally)
- Don't show raw JSON, technical details, or data_source fields to users

Link formatting:
1. Regular link: [headline](url) - Source
2. If 'archive_url' exists (for paywalled sources): Add [🔒](archive_url) after the headline
3. Fallback: [headline](woodchuck_page) - Source (links to our archive)

Example with paywalled source (has archive_url):
"Here are the latest headlines from Spiegel:
• [Germany announces new climate policy](https://spiegel.de/article/123) [🔒](https://archive.is/https://spiegel.de/article/123) - Spiegel
• [Tech giants face EU regulation](https://spiegel.de/article/456) [🔒](https://archive.is/https://spiegel.de/article/456) - Spiegel

The 🔒 links go to archived versions that bypass the paywall. 🦫"

Example with free source (no archive_url):
"Here are the latest headlines from The Guardian:
• [UK announces new trade deal](https://theguardian.com/article/123) - Guardian
• [Climate summit begins today](https://theguardian.com/article/456) - Guardian

🦫"

Example when only archive links available:
"Here are the latest headlines from Spiegel:
• [Germany announces new climate policy](/source/spiegel/) - Spiegel
• [Tech giants face EU regulation](/source/spiegel/) - Spiegel

These link to our headlines archive. 🦫"

Example when tool fails:
"I tried to search for that topic, but couldn't retrieve any results right now. You can browse the latest headlines on the [home page](/) or try a different search term. 🦫"

Available tools:
- get_latest_news: Get the most recent headlines (PREFERRED for general news requests)
- search_news: Search for news by specific keyword (company names, specific terms)
- get_news_by_date: Get all headlines from a specific date  
- get_trending_topics: Find what topics are trending
- get_woodchuck_pages: Find available pages on the site

When users ask about specific sources (like Spiegel, Guardian, etc.):
- Use get_latest_news with the platform filter to get news from that source
- Present the actual headlines from the tool results
- Show 🔒 archive links only when archive_url is present in the data

Be helpful and make news accessible! Never invent news. 🦫"""
