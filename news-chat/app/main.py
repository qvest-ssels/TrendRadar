"""
News Chat - Main FastAPI Application

Provides a web-based chat interface connecting Ollama LLM to TrendRadar MCP.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .web.routes import router as web_router
from .api.routes import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("🗞️ News Chat starting...")
    logger.info(f"   Ollama URL: {settings.ollama_url}")
    logger.info(f"   Model: {settings.ollama_model}")
    logger.info(f"   MCP Server: {settings.mcp_server_url}")
    yield
    logger.info("News Chat shutting down...")


app = FastAPI(
    title="News Chat",
    description="AI-powered chat interface for TrendRadar news analysis",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for cross-origin requests from Woodchuck News
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Include routers
app.include_router(api_router, prefix="/api")
app.include_router(web_router)


@app.get("/")
async def index():
    """Serve the main chat UI."""
    index_file = static_path / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "News Chat API", "docs": "/docs"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "news-chat"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
