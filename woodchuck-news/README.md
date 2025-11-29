# Woodchuck News 🦫

*"How much news could a woodchuck chuck if a woodchuck could chuck news?"*

> ⚠️ **Disclaimer**: This is NOT affiliated with the [Woodchuck News from Sheboygan County Conservation Association](https://sheboyganconservation.org/woodchuck-news/) in Wisconsin. We have no groundhogs, no conservation tips, and definitely no cheese curds. Just news aggregation. Sorry, Wisconsin! 🧀

A static news aggregator frontend for TrendRadar - a playful take on services like Ground News, but focused on browsing cached headlines from multiple international sources.

## What is this?

Woodchuck News is a **read-only web interface** that displays news headlines collected by TrendRadar's crawlers. It generates static HTML pages from cached data, served by nginx for maximum performance and simplicity.

### Key Features

- 📰 **Browse headlines** by date, region, or language
- 🌍 **Regional grouping** - Europe, Asia, Americas, Middle East, Africa, Oceania
- 🔗 **SEO-friendly URLs** - `/news/2025-11-29/eu-announces-new-ai-rules-a7f3`
- ⚡ **Static pages** - Pre-generated HTML, fast and cacheable
- 🐳 **Docker-based** - Easy deployment with docker-compose
- 🎨 **TailwindCSS** - Clean, responsive design

## Architecture

```
┌─────────────────┐     HTTP API      ┌─────────────────┐
│   MCP Server    │◄─────────────────►│  Static Gen     │
│  (port 3333)    │                   │  (Python)       │
└─────────────────┘                   └────────┬────────┘
                                               │
                                               │ generates
                                               ▼
                                      ┌─────────────────┐
                                      │  Static HTML    │
                                      │  (output/)      │
                                      └────────┬────────┘
                                               │
                                               │ serves
                                               ▼
                                      ┌─────────────────┐
                                      │     nginx       │◄──── Users
                                      │  (port 8080)    │
                                      └─────────────────┘
```

The generator fetches data from TrendRadar's MCP API, transforms it into static HTML pages, and nginx serves them. No direct database access, no live scraping - just clean separation of concerns.

## URL Structure

```
/                                    → Today's headlines
/news/2025-11-29/                    → All news for a specific date
/news/2025-11-29/slug-from-title-id  → Single article view
/region/europe/                      → European news (all dates)
/region/europe/2025-11-29/           → European news for specific date
/language/de/                        → German language news
/language/de/2025-11-29/             → German news for specific date
/archive/                            → Browse by date
```

## Region Mapping

Headlines are grouped by geographic region and subregion:

| Region | Subregions | Platforms |
|--------|-----------|-----------|
| **Europe** | DACH, France, UK, Spain | Der Spiegel, Heise, Le Monde, The Guardian, El País |
| **Asia** | China, Japan, Korea, Singapore, India | Toutiao, Baidu, Weibo, Japan Times, Korea Herald, Straits Times, Times of India |
| **Middle East** | Gulf, Israel | Al Jazeera, Asharq Al-Awsat, Times of Israel |
| **Americas** | USA, Brazil, Mexico | Slashdot, Folha, El País México |
| **Oceania** | Australia | The Guardian Australia |
| **Africa** | South Africa | Daily Maverick |

## Quick Start

```bash
# Start the MCP server first (from TrendRadar root)
make start-server

# Then start Woodchuck News
cd woodchuck-news
docker compose up -d

# Generate today's pages
docker compose exec generator python -m generator

# Open in browser
open http://localhost:8080
```

## Development

### Project Structure

```
woodchuck-news/
├── docker-compose.yml      # Container orchestration
├── Dockerfile              # Multi-stage build
├── nginx/
│   ├── nginx.conf          # Main nginx config
│   └── sites/
│       └── default.conf    # Site configuration
├── generator/
│   ├── __init__.py
│   ├── main.py             # CLI entry point
│   ├── api_client.py       # MCP API client
│   ├── models.py           # Data models
│   ├── renderer.py         # HTML generation
│   └── config.py           # Region mapping, settings
├── templates/
│   ├── base.html           # Base template
│   ├── index.html          # Homepage
│   ├── date.html           # Date listing
│   ├── region.html         # Region listing
│   ├── language.html       # Language listing
│   └── article.html        # Single article
├── static/
│   ├── css/
│   │   └── styles.css      # TailwindCSS output
│   └── js/
│       └── main.js         # Minimal JS
└── output/                 # Generated static files
```

### Generator Commands

```bash
# Generate today's pages
python -m generator

# Generate specific date
python -m generator --date 2025-11-29

# Generate date range
python -m generator --from 2025-11-01 --to 2025-11-29

# Watch mode (regenerate periodically)
python -m generator --watch --interval 3600
```

## Roadmap

### Phase 1: Basic Static Site ✅ Planning Complete
- [ ] Project structure
- [ ] Docker + nginx setup
- [ ] MCP API client
- [ ] Basic templates (homepage, date listing)

### Phase 2: Full Feature Set
- [ ] Region/language pages
- [ ] Article detail pages
- [ ] Archive/calendar view
- [ ] Search (static, client-side)

### Phase 3: Interactive Mode (Future)
- [ ] Local-only admin features
- [ ] Trigger crawl from UI
- [ ] Translation integration
- [ ] Bookmark/read tracking

## Why "Woodchuck"?

It's a playful pun on "Ground News" - another news aggregator that compares coverage across sources. Woodchucks (groundhogs) live in the ground, get it? 

Also, we wanted to answer the age-old question: *How much news could a woodchuck chuck if a woodchuck could chuck news?*

The answer: About 30 platforms worth, apparently.

## License

Part of the TrendRadar project. See main repository for license details.
