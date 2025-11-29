"""
SQLite Database Schema for TrendRadar

Provides persistent storage for:
- URL deduplication and tracking
- Headlines with full-text search
- Crawl metadata and statistics
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# Custom datetime adapter/converter for SQLite (Python 3.12+)
def _adapt_datetime(dt: datetime) -> str:
    """Convert datetime to ISO format string for SQLite storage."""
    return dt.isoformat()


def _convert_datetime(data: bytes) -> datetime:
    """Convert ISO format string from SQLite to datetime."""
    return datetime.fromisoformat(data.decode())


# Register adapters - required for Python 3.12+
sqlite3.register_adapter(datetime, _adapt_datetime)
sqlite3.register_converter("DATETIME", _convert_datetime)
sqlite3.register_converter("datetime", _convert_datetime)

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "output" / "trendradar.db"

# Schema version for migrations
SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- URL registry for deduplication
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT UNIQUE NOT NULL,          -- 16-char SHA-256 hash of normalized URL
    normalized_url TEXT NOT NULL,           -- URL with tracking params stripped
    original_url TEXT,                      -- First seen original URL
    domain TEXT NOT NULL,                   -- Extracted domain for indexing
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 1,
    source TEXT DEFAULT 'unknown'           -- 'cached', 'live', 'woodchuck'
);

-- Headlines/news items
CREATE TABLE IF NOT EXISTS headlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id INTEGER REFERENCES urls(id),     -- Foreign key to urls table
    platform_id TEXT NOT NULL,              -- Platform identifier (spiegel, guardian, etc.)
    platform_name TEXT,                     -- Human-readable platform name
    title TEXT NOT NULL,
    rank INTEGER,                           -- Position in the feed
    language TEXT DEFAULT 'en',
    crawl_time DATETIME NOT NULL,
    crawl_date TEXT NOT NULL,               -- YYYY-MM-DD for partitioning
    crawl_file TEXT,                        -- Reference to JSON file
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Crawl sessions for metadata
CREATE TABLE IF NOT EXISTS crawl_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_time DATETIME NOT NULL,
    crawl_date TEXT NOT NULL,
    timezone TEXT DEFAULT 'UTC',
    version TEXT,
    total_platforms INTEGER DEFAULT 0,
    failed_platforms INTEGER DEFAULT 0,
    total_headlines INTEGER DEFAULT 0,
    json_file TEXT,                         -- Path to JSON export
    duration_seconds REAL
);

-- Platform statistics
CREATE TABLE IF NOT EXISTS platform_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_session_id INTEGER REFERENCES crawl_sessions(id),
    platform_id TEXT NOT NULL,
    platform_name TEXT,
    language TEXT,
    item_count INTEGER DEFAULT 0,
    success BOOLEAN DEFAULT 1,
    error_message TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_urls_hash ON urls(url_hash);
CREATE INDEX IF NOT EXISTS idx_urls_domain ON urls(domain);
CREATE INDEX IF NOT EXISTS idx_urls_last_seen ON urls(last_seen);

CREATE INDEX IF NOT EXISTS idx_headlines_platform ON headlines(platform_id);
CREATE INDEX IF NOT EXISTS idx_headlines_crawl_date ON headlines(crawl_date);
CREATE INDEX IF NOT EXISTS idx_headlines_crawl_time ON headlines(crawl_time);
CREATE INDEX IF NOT EXISTS idx_headlines_url ON headlines(url_id);

CREATE INDEX IF NOT EXISTS idx_crawl_sessions_date ON crawl_sessions(crawl_date);
CREATE INDEX IF NOT EXISTS idx_platform_stats_session ON platform_stats(crawl_session_id);

-- Full-text search for headlines
CREATE VIRTUAL TABLE IF NOT EXISTS headlines_fts USING fts5(
    title,
    platform_id,
    platform_name,
    content='headlines',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS headlines_ai AFTER INSERT ON headlines BEGIN
    INSERT INTO headlines_fts(rowid, title, platform_id, platform_name)
    VALUES (new.id, new.title, new.platform_id, new.platform_name);
END;

CREATE TRIGGER IF NOT EXISTS headlines_ad AFTER DELETE ON headlines BEGIN
    INSERT INTO headlines_fts(headlines_fts, rowid, title, platform_id, platform_name)
    VALUES ('delete', old.id, old.title, old.platform_id, old.platform_name);
END;

CREATE TRIGGER IF NOT EXISTS headlines_au AFTER UPDATE ON headlines BEGIN
    INSERT INTO headlines_fts(headlines_fts, rowid, title, platform_id, platform_name)
    VALUES ('delete', old.id, old.title, old.platform_id, old.platform_name);
    INSERT INTO headlines_fts(rowid, title, platform_id, platform_name)
    VALUES (new.id, new.title, new.platform_id, new.platform_name);
END;
"""


class Database:
    """
    SQLite database manager for TrendRadar.
    
    Thread-safe with connection pooling via context manager.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. Defaults to output/trendradar.db
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_directory()
        self._initialized = False
    
    def _ensure_directory(self):
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def connection(self):
        """
        Context manager for database connections.
        
        Ensures proper connection handling and transaction management.
        """
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")  # Better concurrent access
        
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def initialize(self, force: bool = False):
        """
        Initialize database schema.
        
        Args:
            force: If True, recreate schema even if exists
        """
        if self._initialized and not force:
            return
        
        with self.connection() as conn:
            # Check if already initialized
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_info'"
            )
            exists = cursor.fetchone() is not None
            
            if not exists or force:
                logger.info(f"Initializing database schema at {self.db_path}")
                conn.executescript(SCHEMA_SQL)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_info (key, value) VALUES (?, ?)",
                    ("schema_version", str(SCHEMA_VERSION))
                )
                logger.info("Database schema initialized successfully")
            
            self._initialized = True
    
    def get_schema_version(self) -> int:
        """Get current schema version."""
        try:
            with self.connection() as conn:
                cursor = conn.execute(
                    "SELECT value FROM schema_info WHERE key = 'schema_version'"
                )
                row = cursor.fetchone()
                return int(row[0]) if row else 0
        except sqlite3.OperationalError:
            return 0
    
    def vacuum(self):
        """Optimize database by running VACUUM."""
        with self.connection() as conn:
            conn.execute("VACUUM")
        logger.info("Database vacuumed")
    
    def stats(self) -> dict:
        """Get database statistics."""
        with self.connection() as conn:
            stats = {}
            
            # Count tables
            for table in ['urls', 'headlines', 'crawl_sessions', 'platform_stats']:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f'{table}_count'] = cursor.fetchone()[0]
            
            # Database file size
            stats['db_size_bytes'] = self.db_path.stat().st_size if self.db_path.exists() else 0
            stats['db_size_mb'] = round(stats['db_size_bytes'] / (1024 * 1024), 2)
            
            # Date range
            cursor = conn.execute(
                "SELECT MIN(crawl_date), MAX(crawl_date) FROM headlines"
            )
            row = cursor.fetchone()
            stats['date_range'] = {'min': row[0], 'max': row[1]} if row[0] else None
            
            # Top domains
            cursor = conn.execute("""
                SELECT domain, COUNT(*) as cnt 
                FROM urls 
                GROUP BY domain 
                ORDER BY cnt DESC 
                LIMIT 10
            """)
            stats['top_domains'] = [{'domain': r[0], 'count': r[1]} for r in cursor.fetchall()]
            
            return stats


# Global database instance
_db: Optional[Database] = None


def get_database(db_path: Optional[Path] = None) -> Database:
    """
    Get the global database instance.
    
    Args:
        db_path: Optional custom database path
        
    Returns:
        Initialized Database instance
    """
    global _db
    
    if _db is None or (db_path and db_path != _db.db_path):
        _db = Database(db_path)
        _db.initialize()
    
    return _db


def reset_database():
    """Reset the global database instance (for testing)."""
    global _db
    _db = None
