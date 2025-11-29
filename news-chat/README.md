# News Chat 🗞️💬

AI-powered chat interface for TrendRadar news analysis using local LLMs.

## Overview

News Chat provides a web-based chat interface that connects a local LLM (via Ollama) 
to the TrendRadar MCP server, enabling natural language queries about news headlines.

```
┌─────────────────────────────────────────────────────────┐
│                    News Chat Stack                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   User ──▶ Web UI ──▶ FastAPI ──▶ LLM (Ollama)         │
│              │                        │                  │
│              │                        ▼                  │
│              │               Tool Calling                │
│              │                        │                  │
│              │                        ▼                  │
│              └────────────────▶ TrendRadar MCP          │
│                                    :3333                │
└─────────────────────────────────────────────────────────┘
```

## Features

- 🤖 **Local LLM** - Runs on your Mac via Ollama (qwen2.5:14b recommended)
- 🔧 **Tool Calling** - LLM decides when to query TrendRadar for news
- 🌐 **Web UI** - Clean chat interface with TailwindCSS
- 🔄 **Streaming** - Real-time response streaming
- 🌍 **Multilingual** - Query in English, German, Chinese, etc.

## Prerequisites

1. **Ollama** installed and running:
   ```bash
   # Install Ollama (macOS)
   brew install ollama
   
   # Start Ollama service
   ollama serve
   
   # Pull recommended model (10GB, fits in 24GB RAM)
   ollama pull qwen2.5:14b
   
   # Or smaller model for faster responses (5GB)
   ollama pull qwen2.5:7b
   ```

2. **TrendRadar MCP Server** running:
   ```bash
   cd /path/to/TrendRadar
   make start-server
   ```

## Quick Start

### Local Development

```bash
cd news-chat

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Run the server
python -m app.main
```

Open http://localhost:8000 in your browser.

### Docker

```bash
# Build and run
docker-compose up -d

# Or with the full TrendRadar stack
cd .. && docker-compose -f docker/docker-compose-full.yml up -d
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Model to use |
| `MCP_SERVER_URL` | `http://localhost:3333` | TrendRadar MCP server |
| `API_KEY` | (optional) | API key for cloud LLM fallback |

## Example Queries

- "What are today's top tech headlines?"
- "搜索关于人工智能的新闻" (Search for AI news)
- "Zeige mir deutsche Nachrichten über Tesla" (Show German news about Tesla)
- "Compare coverage of climate change between European and US sources"
- "What's trending in Asia-Pacific today?"
- "Summarize the top 5 headlines from Der Spiegel"

## Architecture

```
news-chat/
├── app/
│   ├── main.py           # FastAPI application
│   ├── llm/
│   │   ├── client.py     # LLM client (Ollama/API)
│   │   └── tools.py      # MCP tool definitions
│   ├── mcp/
│   │   └── client.py     # MCP client for TrendRadar
│   └── web/
│       └── routes.py     # Web UI routes
├── static/
│   └── index.html        # Chat UI
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## RAM Requirements

| Model | RAM Usage | Response Speed |
|-------|-----------|----------------|
| `qwen2.5:7b` | ~5GB | Fast |
| `qwen2.5:14b` | ~10GB | Medium |
| `qwen2.5:32b` | ~22GB | Slow (64GB Mac) |

For 24GB Mac, `qwen2.5:14b` is recommended.
