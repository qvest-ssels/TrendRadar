"""
MCP Server Data Layer

Provides persistent storage for headlines, URLs, and crawl data.
"""

from .schema import Database, get_database, reset_database, DEFAULT_DB_PATH
from .store import (
    DataStore, 
    get_data_store, 
    reset_data_store,
    HeadlineItem,
    CrawlResult,
)

__all__ = [
    # Schema
    "Database",
    "get_database",
    "reset_database",
    "DEFAULT_DB_PATH",
    # Store
    "DataStore",
    "get_data_store",
    "reset_data_store",
    # Data types
    "HeadlineItem",
    "CrawlResult",
]
