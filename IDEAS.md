# Ideas for Future Development

## News Chat Enhancements

### Deep Search
- Add icon/button on headlines to trigger deep search on specific topics
- Search across multiple sources for related articles
- Show timeline of how story developed

### Alternative Sources
- Find same story from different news outlets
- Show different perspectives on the same event
- Cross-reference headlines across regions

### Article Previews
- Try to fetch excerpt/summary of articles
- Show first paragraph or description when available
- Preview on hover or expand

### Source Metadata Improvements
- Link to source homepage (not per-article)
- Wikipedia link for news organizations
- Country/region of publication
- Language indicator
- Bias/perspective indicators (left, center, right)

## AI-Powered Features (Later)

### User Personalization
- Bookmarks and saved articles
- Reading history
- Custom topic subscriptions

### Recommendations
- "You might also be interested in..."
- Related topics based on reading patterns
- Breaking news alerts for followed topics

### Dynamic Sentiment
- Real-time sentiment analysis on topics
- Mood/tone indicators on headlines
- Track how sentiment changes over time

### Smart Summaries
- AI-generated daily briefings
- Topic-based news digests
- "Catch up" feature for missed days

## Technical Improvements

- Improve energy cycle visibility/meaning
- Add more platform sources
- Better error handling and fallbacks
- Offline/cache support for read articles

## Knowledge Database

### Wikipedia Service Improvements
- Fix image rendering in chat (markdown images not displaying)
- Better formatting of Wikipedia results in LLM responses
- Fallback to search when exact title not found
- Multi-language auto-detection based on user query

### Wikipedia Caching
- When fetching long Wikipedia articles, store them locally
- Build a local knowledge base from frequently accessed topics
- Cache context for news-related entities (companies, people, places)
- Use cached knowledge to reduce API calls and improve response time
- Consider SQLite FTS for searching cached knowledge
- Auto-expire entries after X days, refresh on demand

---

## Ask an Expert - Future Services

### Udemy Course Lookup
- Search for courses by topic/skill
- Get course ratings, reviews, instructor info
- Find tutorials for specific technologies
- Integration: `search_udemy(query, category, level, min_rating)`
- Web scraping or unofficial API
- Use cases: "Find a Python async course", "Best courses for Kubernetes"

### Tech Conference Search
- Search upcoming/past tech conferences
- Conference talks, speakers, schedules
- Sources: Confs.tech, PaperCall, Lanyrd archives
- Integration: `search_conferences(topic, location, date_range)`
- Get talk abstracts and slide decks when available
- Use cases: "AI conferences in 2025", "Find talks about RAG systems"

### Newsletter Discovery
- Find relevant newsletters by topic
- Sources: Substack, Buttondown, newsletter directories
- Integration: `search_newsletters(topic, frequency)`
- Get recent issues/archives
- Use cases: "AI newsletters", "Best tech newsletters for ML engineers"

### IMDB Integration (Fun)
- Movie/TV show search and info
- Ratings, cast, reviews
- Integration: `search_imdb(query, type)`, `get_movie_info(imdb_id)`
- Use cases: "What's the rating for X?", "Movies about AI"
- Could correlate news with related movies/documentaries

### Other Ideas
- **Stack Overflow** - Technical Q&A (in TODOs.md backlog)
- **PubMed** - Medical/scientific papers
- **Semantic Scholar** - Academic papers with citation graphs
- **Product Hunt** - New products and startups
- **Hacker News** - Tech discussion and trends

---

## Fact Checker Service

### Concept
A dedicated fact-checking service that verifies claims and provides sources.

### Features
- **Claim verification** - Analyze statements for factual accuracy
- **Source citation** - Return links/references for each fact
- **Confidence scoring** - Rate how certain the verification is
- **Multi-source cross-reference** - Check against Wikipedia, news archives, official sources
- **Contradiction detection** - Flag when sources disagree

### Integration Ideas
- `fact_check(claim)` → Returns: verdict, confidence, sources[]
- Cross-reference with Wikipedia, news archives, official government sites
- Use multiple search engines for source diversity
- Cache verified facts with TTL for common claims
- Could integrate with existing services (Wikipedia, arXiv for scientific claims)

### Use Cases
- "Is it true that X happened?"
- "Verify this statistic about Y"
- "What are the sources for claim Z?"
- Auto-fact-check headlines before displaying

---

## User Management (Woodchuck News)

### Concept
Add user accounts to Woodchuck News for personalized experience.

### Phase 1: Local Mock Users (Development)
- Simple username/password auth (no external deps)
- SQLite user table with hashed passwords
- Session tokens in browser localStorage
- Mock users: admin, demo, guest

### Phase 2: User Features
- **Saved Links** - Bookmark articles for later
- **Saved Answers** - Store chat responses/research results
- **Preferences** - Default language, favorite topics, display settings
- **Reading History** - Track what was read (optional)
- **Custom Alerts** - Notifications for specific topics

### Phase 3: SSO Integration
- OAuth2/OIDC support (Google, GitHub, corporate)
- Keep local auth as fallback
- Migration path from mock users to SSO

### Data Model
```
User: id, username, email, password_hash, created_at, last_login
SavedLink: id, user_id, url, title, saved_at, tags[]
SavedAnswer: id, user_id, query, response, created_at
Preference: user_id, key, value
```

### API Endpoints
- POST /auth/login, /auth/logout, /auth/register
- GET/POST /user/links, /user/answers, /user/preferences

---

## Bug & Feature Reporting

### Concept
Built-in feedback mechanism for users to report bugs and request features.

### Features
- **Bug Reports** - Describe issue, attach context (current page, last query)
- **Feature Requests** - Suggest improvements
- **Auto-capture context** - Browser info, timestamps, session ID
- **Priority/severity** - User can indicate urgency
- **Status tracking** - Open, In Progress, Resolved, Won't Fix

### Storage Options
- SQLite for local development
- Optional GitHub Issues integration (auto-create issues)
- Optional webhook to Slack/Discord for alerts

### UI Components
- Floating feedback button in News Chat
- Modal form for bug/feature submission
- Admin view to manage reports (dev mode only)

### Data Model
```
Report: id, type (bug|feature), title, description, 
        context_json, user_id, status, created_at, resolved_at
```

### API Endpoints
- POST /feedback/report
- GET /feedback/reports (admin only)
- PATCH /feedback/reports/{id}/status

---

## Development vs Production Mode

### Concept
Clear separation between development and production for non-readonly services.

### Services Affected
- User management (auth, preferences)
- Bug/feature reporting
- Any future write operations (bookmarks, etc.)
- Admin/debug endpoints

### Implementation
- **Environment variable**: `TRENDRADAR_MODE=development|production`
- **Config flag**: `config.yaml` → `mode: development`

### Development Mode Features
- Mock authentication (any password works)
- SQLite for all storage (no external deps)
- Debug endpoints exposed (/debug/*, /admin/*)
- Verbose logging
- Auto-create demo data
- No rate limiting
- CORS allows localhost

### Production Mode Features
- Real authentication required
- Database connection pooling
- Debug endpoints disabled
- Structured logging (JSON)
- Rate limiting enabled
- CORS restricted to configured domains
- HTTPS required for auth endpoints

### Safety Checks
- Startup warning if production mode with SQLite
- Refuse to start if SSO configured but not in production
- Log mode prominently on startup
