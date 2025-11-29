#!/bin/bash
# Run News Chat locally

set -e

echo "🦫 Starting News Chat..."

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama not detected. Starting Ollama..."
    ollama serve &
    sleep 3
fi

# Check if model is available
MODEL="qwen2.5:14b"
if ! ollama list | grep -q "$MODEL"; then
    echo "📥 Pulling $MODEL (this may take a while)..."
    ollama pull $MODEL
fi

# Check if MCP server is running
if ! curl -s http://localhost:3333/health > /dev/null 2>&1; then
    echo "⚠️  TrendRadar MCP server not running on port 3333"
    echo "   Start it with: python main.py --transport http --port 3333"
    echo "   Continuing anyway (chat will work without tool calls)..."
fi

# Install dependencies if needed
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    uv venv .venv
fi

source .venv/bin/activate

echo "📦 Installing dependencies..."
uv pip install -r requirements.txt

echo "🚀 Starting server on http://localhost:8000"
uvicorn app.main:app --reload --port 8000
