# TrendRadar TODOs

## MCP Language Awareness
- [x] **Add language filtering to deep_search** - ✅ DONE
  - Config has `language` field per platform (e.g., "de", "en", "zh", "fr")
  - `deep_search` now supports `language` parameter: `deep_search(query="AI", language="de")`
  - Returns language info in results metadata
  - Added `get_platform_language()` and updated `get_searchable_platforms(language=)`

## CDN Detection
- [x] **Add `cdn` field to config** - ✅ DONE (partial)
  - Added `cdn: "cloudflare"` to platforms with known Cloudflare protection
  - Platforms marked: timesofisrael, dailymaverick, aawsat
- [ ] **Use CDN info in browser service**
  - Auto-apply extra stealth/wait time for Cloudflare sites
  - Consider proxy rotation for Cloudflare-protected sites
  - Log CDN type when search fails for debugging

## Platform Search Status

### Working (7 platforms)
- ✅ The Guardian (API) - en
- ✅ Spiegel (JS/Stealth) - de
- ✅ Al Jazeera (JS/Stealth) - en
- ✅ Heise (JS/Stealth) - de
- ✅ Le Monde (JS/Stealth) - fr
- ✅ Straits Times (JS/Stealth) - en
- ✅ Times of India (URL pattern) - en

### Disabled (need work)
- ❌ Tagesspiegel - JS search broken (uses complex React framework)
- ❌ Moscow Times - Search page only shows contribution banners
- ❌ Times of Israel - Cloudflare blocks even with stealth mode (cdn: cloudflare)
- ❌ Daily Maverick - Cloudflare protection (cdn: cloudflare)
- ❌ Asharq Al-Awsat - Cloudflare protection (cdn: cloudflare)
- ❌ Folha - Cloudflare protection (cdn: cloudflare)

### Not yet tested
- ⏳ Guardian AU - Can use same API as Guardian

## Future Improvements
- [ ] Add more platforms with working search
- [ ] Consider browserless.io for stubborn Cloudflare sites
- [ ] Add proxy rotation support for rate-limited sites
- [ ] Cache search results to reduce duplicate requests
- [ ] Auto-detect CDN from response headers

---

## Ask an Expert 🧑‍🔬

An advanced research feature for technical/scientific queries that go beyond news aggregation.

### Concept
When users ask questions that need expert-level research (not just news), this feature searches:
- **Hugging Face** - Find models, datasets, papers related to ML/AI topics
- **arXiv** - Search academic papers for scientific/technical topics
- **GitHub** - Find relevant repos, code examples, tools
- **Stack Overflow** - Technical Q&A for programming questions
- **PubMed** - Medical/biomedical research papers

### Use Cases
- "What's the best LLM for code generation?" → Search HuggingFace models + benchmarks
- "Latest research on transformer architectures" → arXiv papers
- "How do I implement RAG?" → GitHub repos + Stack Overflow
- "Clinical trials for cancer treatment X" → PubMed papers

### Phase 1: HuggingFace Integration ✅ DONE
- [x] **1.1 Create HuggingFace service** - `mcp_server/services/huggingface_service.py`
  - Search models by task (text-generation, translation, etc.)
  - Search datasets
  - Get daily papers and search papers
  - XSS sanitization for all responses
- [x] **1.2 Add MCP tools** - 3 tools added:
  - `search_huggingface_models(query, task, sort, limit)`
  - `search_huggingface_datasets(query, sort, limit)`
  - `get_ml_papers(query, limit)`
- [x] **1.3 Integrate into News Chat** - Added to system prompt as expert resource
- [x] **1.4 Tests** - 16 tests in `tests/test_huggingface_service.py`

### Phase 2: arXiv Papers ✅ DONE
- [x] **2.1 Create arXiv service** - `mcp_server/services/arxiv_service.py`
  - Search papers by query/category
  - Get abstracts and PDF links
  - University linking via Wikipedia
  - XSS sanitization for all responses
- [x] **2.2 Add MCP tools** - `search_arxiv(query, category, max_results)`, `get_arxiv_paper(arxiv_id)`
- [x] **2.3 Categories**: cs.AI, cs.CL, cs.LG, cs.CV, cs.NE, stat.ML, cs.IR, cs.SE
- [x] **2.4 Tests** - 39 tests in `tests/test_arxiv_service.py`

### Phase 3: GitHub Search ✅ DONE
- [x] **3.1 Create GitHub service** - `mcp_server/services/github_service.py`
  - Search repos by topic/keywords
  - Get README summaries
  - Rate limiting (10 req/min unauthenticated, 30 with token)
- [x] **3.2 Add MCP tool** - `search_github_repos(query, language, sort, limit, min_stars)`
- [x] **3.3 Tests** - 44 tests in `tests/test_github_service.py`

### Phase 3.5: API Caching ✅ DONE
- [x] **3.5.1 Create cache utility** - `mcp_server/utils/cache.py`
  - TTLCache class with time-based expiration
  - Named caches for service isolation (github, arxiv, huggingface)
  - Max size limits with LRU-style eviction
  - Hit/miss stats tracking
- [x] **3.5.2 Add cache to services**
  - GitHub: 1 hour TTL, caches search_repos
  - arXiv: 30 min TTL, caches search
  - HuggingFace: 1 hour TTL, caches search_models, search_datasets
- [x] **3.5.3 Cache stats endpoint** - GET `/cache/stats`
- [x] **3.5.4 Tests** - 13 tests in `tests/test_cache.py`

### Phase 3.6: Expert Research ✅ DONE
- [x] **3.6.1 Create expert_research meta-tool**
  - Combines arXiv + GitHub + HuggingFace in parallel async calls
  - Cross-references results (marks repos implementing papers)
  - Intelligent source selection based on query type
- [x] **3.6.2 Integrate into News Chat**
  - Added expert_research tool definition
  - System prompt prioritizes it for broad technical questions

### Phase 3.7: YouTube Context ✅ DONE
- [x] **3.7.1 Create YouTube service** - `mcp_server/services/youtube_service.py`
  - Search videos via web scraping (no API key needed)
  - Extract transcripts via youtube-transcript-api v1.x
  - Sanitize HTML/URL to prevent XSS
  - Cache transcripts (24hr TTL)
- [x] **3.7.2 Add MCP tools**
  - `search_youtube(query, limit)` - Find educational videos
  - `get_youtube_transcript(video_id)` - Extract spoken content
- [x] **3.7.3 Tests** - 31 tests in `tests/test_youtube_service.py`
- [x] **3.7.4 Use Cases**
  - Find tutorials: "search_youtube('python async tutorial')"
  - Get content without watching: "get_youtube_transcript('dQw4w9WgXcQ')"
  - Research conference talks, lectures, explainers

### Phase 3.8: Learning & Discovery Services ✅ DONE
- [x] **3.8.1 Udemy Course Search** - `mcp_server/services/udemy_service.py`
  - Search courses by topic via web scraping
  - Filter by level (beginner, intermediate, expert)
  - Filter by rating, free/paid
  - Tool: `search_udemy(query, level, min_rating, free_only)`
- [x] **3.8.2 Tech Conference Search** - `mcp_server/services/conference_service.py`
  - Search conferences via confs.tech API (free, no key needed)
  - Filter by topic, year, country, city
  - Get CFP deadlines
  - Tool: `search_conferences(topic, year, country, city)`
- [x] **3.8.3 Newsletter Discovery** - `mcp_server/services/newsletter_service.py`
  - Search newsletters via Substack scraping
  - Curated list of popular tech newsletters
  - Tools: `search_newsletters(query)`, `get_popular_newsletters(category)`
- [x] **3.8.4 IMDB/Movie Search** - `mcp_server/services/imdb_service.py`
  - Search movies/TV shows via OMDb API
  - Get detailed info (plot, cast, ratings)
  - Requires free API key from omdbapi.com
  - Tools: `search_movies(query, type)`, `get_movie_details(imdb_id)`
- [x] **3.8.5 IMDB Person Search** - Enhanced `mcp_server/services/imdb_service.py`
  - Search actors/directors via IMDB web scraping
  - Cross-reference with Wikipedia for bios
  - Get filmography from person pages
  - Tools: `search_person(name, include_wikipedia)`, `get_person_filmography(imdb_id, limit)`
- [x] **3.8.6 Tests** - 38 tests in `tests/test_new_services.py`

### Phase 4: Stack Overflow (Backlog)
- [ ] **4.1 Create StackOverflow service** - `mcp_server/services/stackoverflow_service.py`
  - Search questions by tags/keywords
  - Get top answers
  - API: https://api.stackexchange.com/2.3/search
- [ ] **4.2 Add MCP tool** - `search_stackoverflow(query, tags, limit)`

### Future Extensions
- [ ] **PubMed** for medical research
- [ ] **Semantic Scholar** for academic papers
- [ ] **Papers With Code** for ML papers with implementations
- [ ] **Result synthesis** - Combine results from multiple sources into summary

### Technical Notes
- All services should have XSS sanitization (like Wikipedia service)
- HTTP timeouts: 10-15 seconds
- Rate limiting awareness for free APIs
- ✅ API responses cached to reduce calls (TTLCache, 30min-1hr TTL)
- ✅ expert_research combines multiple sources with parallel async

---

## Wikipedia Knowledge Service

### Improvements Needed
- [ ] **Fix image rendering in chat** - Markdown images not displaying in News Chat
- [ ] **Better formatting of Wikipedia results** - LLM not consistently following format instructions
- [ ] **Fallback to search** - When exact title not found, use search API
- [ ] **Multi-language auto-detection** - Detect user's query language and use matching Wikipedia

### Future Enhancements
- [ ] **Wikipedia Caching** - Store fetched articles locally in SQLite FTS
- [ ] **Knowledge base** - Build cache of frequently accessed topics (companies, people, places)
- [ ] **Auto-expire** - TTL-based cache invalidation, refresh on demand
- [ ] **Reduce API calls** - Use cached knowledge for repeated queries

---

## Translation Service Integration

### Overview
Modular translation service supporting both local and remote backends, starting with LibreTranslate for local/self-hosted translation.

### Phase 1: Infrastructure Setup
- [x] **1.1 Create translation service directory structure** ✅ DONE
  - Created `mcp_server/services/translation_service.py`
  - TranslationService class with singleton pattern
  - Methods: `translate()`, `translate_batch()`, `detect_language()`, `get_languages()`

- [x] **1.2 Test LibreTranslate with Colima/Docker on ARM** ✅ DONE
  - Tested with Colima on macOS ARM64 (aarch64)
  - Cloned upstream: `libretranslate-upstream/` (gitignored)
  - Key fix: `tty: true` required for docker logs to show
  - Key fix: Port 5000 conflicts with AirPlay on macOS → use 5555
  - Models cached in Docker volume for fast restarts

- [x] **1.3 Create LibreTranslate docker-compose for TrendRadar** ✅ DONE
  - Added `docker/docker-compose-libretranslate.yml`
  - Cloned upstream repo to `libretranslate-upstream/` with working config
  - Volume: `libretranslate_models:/home/libretranslate/.local:rw`
  - Languages: en, de, zh, fr, es (5 languages, 8 models)
  - API tested: `/health`, `/languages`, `/translate` all working
  - Start: `cd libretranslate-upstream && docker compose up -d`

### Phase 2: Translation Service Implementation
- [x] **2.1 Create base translation interface** ✅ DONE
  - `mcp_server/services/translation_service.py` - TranslationService class
  - Methods: `translate(text, source, target)`, `detect_language(text)`, `get_languages()`
  - Batch translation via `translate_batch()`
  - Health check via `is_available()`

- [x] **2.2 Implement LibreTranslate adapter** ✅ DONE
  - HTTP client for LibreTranslate API (`/translate`, `/detect`, `/languages`)
  - Connection health check, timeout handling
  - Singleton pattern via `get_translation_service()`

- [ ] **2.3 Create translation service factory** (optional for future)
  - Config-driven backend selection (local/remote)
  - Support for fallback chains (local -> remote)
  - Easy extensibility for future backends (DeepL, Google, etc.)

### Phase 3: MCP Integration
- [x] **3.1 Add translation config to config.yaml** ✅ SKIPPED
  - Using default URL http://localhost:5555 in code
  - Can be made configurable later if needed

- [x] **3.2 Create MCP translation tools** ✅ DONE
  - `translate_text(text, source, target)` - Translate single text
  - `translate_headlines(date, target_language)` - Translate cached headlines
  - `get_translation_languages()` - Get available languages

- [ ] **3.3 Integrate translation into existing tools** (future)
  - Add optional `translate_to` parameter to `deep_search`
  - Add translation option to `meta_search` results
  - Auto-detect and translate non-English headlines when requested

### Phase 4: Future Extensions
- [ ] **4.1 Remote translation backends**
  - DeepL API adapter (high quality, requires API key)
  - Google Translate API adapter (requires credentials)
  - Azure Translator adapter

- [ ] **4.2 Translation caching**
  - Cache translations to avoid duplicate API calls
  - Use same SQLite cache as headlines
  - TTL-based cache invalidation

- [ ] **4.3 Quality/Cost optimization**
  - Prefer local translation for common language pairs
  - Fallback to remote for unsupported pairs
  - Rate limiting for remote API costs

### Technical Notes
- **LibreTranslate ARM64**: Uses `docker/arm.Dockerfile` with `arm64v8/python:3.11.11-slim-bullseye`
- **Docker command**: `docker run -ti --rm -p 5000:5000 -v lt-local:/home/libretranslate/.local libretranslate/libretranslate --load-only en,de,zh,fr,es`
- **API Endpoints**:
  - `POST /translate` - `{q: "text", source: "en", target: "de"}`
  - `POST /detect` - `{q: "text"}`
  - `GET /languages` - List supported languages
- **Memory**: ~2GB with all models, ~500MB with limited languages
- **First startup**: Downloads language models (~1-2GB)

---

## Woodchuck News - Static News Aggregator Frontend 🦫

*"How much news could a woodchuck chuck if a woodchuck could chuck news?"*

A play on Ground News - a static site generator + nginx web server for browsing cached headlines.

### Overview
- **Subfolder**: `woodchuck-news/`
- **Architecture**: Python static generator + nginx + Docker
- **Data source**: MCP API only (HTTP calls to `localhost:3333`)
- **Output**: Static HTML pages with TailwindCSS
- **Caching**: nginx serves pre-generated pages

### URL Structure (Option A: Date-first)
```
/                                          # Homepage - today's headlines
/news/2025-11-29/                          # All headlines for date
/news/2025-11-29/slug-from-title-{id}      # Single article view
/region/europe/                            # Region index
/region/europe/2025-11-29/                 # Region + date
/language/de/                              # Language index  
/language/de/2025-11-29/                   # Language + date
/archive/                                  # Date picker / calendar
```

### Region Mapping (Custom by Continent/Region)
```yaml
regions:
  europe:
    name: "Europe"
    subregions:
      dach: ["spiegel", "heise", "tagesspiegel"]  # DE/AT/CH
      france: ["lemonde"]
      uk: ["theguardian"]
      spain: ["elpais"]
  
  asia:
    name: "Asia"
    subregions:
      china: ["toutiao", "baidu", "weibo", "zhihu", "bilibili-hot-search", "douyin"]
      japan: ["japantimes"]
      korea: ["koreaherald"]
      singapore: ["straitstimes"]
      india: ["timesofindia"]
  
  middle_east:
    name: "Middle East"
    subregions:
      gulf: ["aljazeera", "aawsat"]
      israel: ["timesofisrael"]
  
  americas:
    name: "Americas"
    subregions:
      usa: ["slashdot"]
      brazil: ["folha"]
      mexico: ["elpais_mexico"]
  
  oceania:
    name: "Oceania"
    subregions:
      australia: ["guardianau"]
  
  africa:
    name: "Africa"
    subregions:
      south_africa: ["dailymaverick"]
```

### Phase 1: Infrastructure Setup
- [ ] **1.1 Create project structure**
  ```
  woodchuck-news/
  ├── docker-compose.yml
  ├── Dockerfile
  ├── nginx/
  │   ├── nginx.conf
  │   └── sites/
  │       └── default.conf
  ├── generator/
  │   ├── __init__.py
  │   ├── main.py           # Entry point
  │   ├── api_client.py     # MCP API client
  │   ├── models.py         # Data models
  │   ├── renderer.py       # HTML generation
  │   └── config.py         # Region mapping, settings
  ├── templates/
  │   ├── base.html
  │   ├── index.html        # Homepage
  │   ├── date.html         # Date listing
  │   ├── region.html       # Region listing
  │   ├── language.html     # Language listing
  │   └── article.html      # Single article
  ├── static/
  │   ├── css/
  │   │   └── tailwind.css
  │   └── js/
  │       └── main.js
  └── output/               # Generated static files
      └── .gitkeep
  ```

- [ ] **1.2 Create Docker setup**
  - Multi-stage build: Python generator + nginx
  - Volume for output directory
  - Health checks

- [ ] **1.3 Create nginx configuration**
  - Static file serving from `/output`
  - URL rewriting for clean URLs
  - Date parsing from URL path
  - Cache headers for static content
  - Gzip compression

### Phase 2: Static Generator
- [ ] **2.1 MCP API Client**
  - `get_news_by_date(date)` - Fetch headlines
  - `get_platforms()` - Get platform list
  - Error handling, retries, timeouts

- [ ] **2.2 URL/Slug Generation**
  - Slugify titles (ASCII, lowercase, hyphens)
  - Unique ID suffix (short hash or position)
  - Example: `eu-announces-new-ai-regulations-a7f3`

- [ ] **2.3 HTML Renderer**
  - Jinja2 templates
  - TailwindCSS styling
  - Responsive design
  - Dark/light mode

- [ ] **2.4 Generator CLI**
  ```bash
  # Generate today
  python -m generator
  
  # Generate specific date
  python -m generator --date 2025-11-29
  
  # Generate date range
  python -m generator --from 2025-11-01 --to 2025-11-29
  
  # Watch mode (regenerate on interval)
  python -m generator --watch --interval 3600
  ```

### Phase 3: Page Templates
- [ ] **3.1 Homepage**
  - Today's top headlines
  - Quick region/language filters
  - Recent dates navigation

- [ ] **3.2 Date listing**
  - All headlines for a date
  - Grouped by region or language
  - Sortable (time, platform, region)

- [ ] **3.3 Region/Language pages**
  - Headlines filtered by region/language
  - Platform breakdown within region

- [ ] **3.4 Article page** (optional)
  - Single headline with metadata
  - Link to original source
  - Related headlines (same topic/date)

### Phase 4: Interactive Mode (Future)
- [ ] **4.1 Local-only features**
  - Trigger crawl button
  - Search interface
  - Translation toggle
  - Mark as read/bookmark

- [ ] **4.2 API endpoints for interactivity**
  - `/api/crawl` - Trigger crawl
  - `/api/translate` - Translate headline
  - `/api/search` - Search headlines

### Technical Notes
- **nginx date parsing**: Use `location ~ ^/news/(\d{4}-\d{2}-\d{2})/` regex
- **Cache strategy**: 
  - Today's pages: short TTL (5 min)
  - Historical pages: long TTL (1 day)
  - Static assets: immutable
- **TailwindCSS**: Use CDN or build step
- **ID generation**: `hashlib.sha256(url)[:8]` for stable IDs
