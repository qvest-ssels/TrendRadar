"""
DataStore - Unified data access layer for TrendRadar

Handles:
- Storing headlines to both SQLite and files
- URL deduplication with persistent registry
- Full-text search across headlines
- Crawl session management
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

from .schema import Database, get_database
from ..utils.url_utils import normalize_url, url_hash, extract_domain

logger = logging.getLogger(__name__)


@dataclass
class HeadlineItem:
    """A single headline/news item."""
    title: str
    url: str
    platform_id: str
    platform_name: str = ""
    rank: int = 0
    language: str = "en"
    mobile_url: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass 
class CrawlResult:
    """Result of a crawl session."""
    crawl_time: datetime
    platforms: Dict[str, List[HeadlineItem]]
    timezone: str = "UTC"
    version: str = ""
    failed_platforms: List[str] = None
    
    def __post_init__(self):
        if self.failed_platforms is None:
            self.failed_platforms = []


class DataStore:
    """
    Unified data store for TrendRadar.
    
    Provides dual-write capability: writes to both SQLite (for queries)
    and JSON files (for backward compatibility and static serving).
    """
    
    def __init__(self, db: Optional[Database] = None, output_dir: Optional[Path] = None):
        """
        Initialize DataStore.
        
        Args:
            db: Database instance (uses global if not provided)
            output_dir: Output directory for files (defaults to output/)
        """
        self.db = db or get_database()
        self.output_dir = output_dir or Path(__file__).parent.parent.parent / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    # ========== URL Management ==========
    
    def register_url(self, url: str, source: str = "unknown") -> Tuple[int, str, bool]:
        """
        Register a URL in the database.
        
        Args:
            url: The URL to register
            source: Source identifier ('cached', 'live', 'woodchuck')
            
        Returns:
            Tuple of (url_id, url_hash, is_new)
        """
        normalized = normalize_url(url)
        hash_key = url_hash(normalized, normalize=False)
        domain = extract_domain(normalized)
        
        with self.db.connection() as conn:
            # Try to get existing
            cursor = conn.execute(
                "SELECT id FROM urls WHERE url_hash = ?",
                (hash_key,)
            )
            row = cursor.fetchone()
            
            if row:
                # Update existing
                conn.execute("""
                    UPDATE urls 
                    SET last_seen = CURRENT_TIMESTAMP,
                        access_count = access_count + 1,
                        source = CASE WHEN source != ? THEN source || ',' || ? ELSE source END
                    WHERE url_hash = ?
                """, (source, source, hash_key))
                return row[0], hash_key, False
            else:
                # Insert new
                cursor = conn.execute("""
                    INSERT INTO urls (url_hash, normalized_url, original_url, domain, source)
                    VALUES (?, ?, ?, ?, ?)
                """, (hash_key, normalized, url, domain, source))
                return cursor.lastrowid, hash_key, True
    
    def lookup_url(self, url: str) -> Optional[dict]:
        """
        Look up a URL in the database.
        
        Args:
            url: URL to look up
            
        Returns:
            URL record or None
        """
        normalized = normalize_url(url)
        hash_key = url_hash(normalized, normalize=False)
        
        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM urls WHERE url_hash = ?",
                (hash_key,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def find_cached_url(self, url: str) -> Optional[str]:
        """
        Find cached version of a URL.
        
        Args:
            url: URL to find cached version for
            
        Returns:
            Normalized URL if found in cache, None otherwise
        """
        record = self.lookup_url(url)
        if record and 'cached' in record.get('source', ''):
            return record['normalized_url']
        return None
    
    def get_urls_by_domain(self, domain: str, limit: int = 100) -> List[dict]:
        """Get all URLs for a domain."""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM urls 
                WHERE domain = ? 
                ORDER BY last_seen DESC 
                LIMIT ?
            """, (domain.lower(), limit))
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== Headlines Management ==========
    
    def store_headlines(
        self,
        headlines: List[HeadlineItem],
        platform_id: str,
        platform_name: str,
        crawl_time: datetime,
        crawl_session_id: Optional[int] = None,
        source: str = "cached"
    ) -> int:
        """
        Store headlines in the database.
        
        Args:
            headlines: List of HeadlineItem objects
            platform_id: Platform identifier
            platform_name: Human-readable platform name
            crawl_time: When the crawl occurred
            crawl_session_id: Optional session ID
            source: Source for URL registration
            
        Returns:
            Number of headlines stored
        """
        crawl_date = crawl_time.strftime("%Y-%m-%d")
        stored = 0
        
        with self.db.connection() as conn:
            for item in headlines:
                # Register URL first
                url_id = None
                if item.url:
                    cursor = conn.execute(
                        "SELECT id FROM urls WHERE url_hash = ?",
                        (url_hash(normalize_url(item.url)),)
                    )
                    row = cursor.fetchone()
                    if row:
                        url_id = row[0]
                    else:
                        # Insert URL
                        normalized = normalize_url(item.url)
                        cursor = conn.execute("""
                            INSERT INTO urls (url_hash, normalized_url, original_url, domain, source)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            url_hash(normalized, normalize=False),
                            normalized,
                            item.url,
                            extract_domain(normalized),
                            source
                        ))
                        url_id = cursor.lastrowid
                
                # Insert headline
                conn.execute("""
                    INSERT INTO headlines 
                    (url_id, platform_id, platform_name, title, rank, language, crawl_time, crawl_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    url_id,
                    platform_id,
                    platform_name or item.platform_name,
                    item.title,
                    item.rank,
                    item.language,
                    crawl_time,
                    crawl_date
                ))
                stored += 1
        
        logger.debug(f"Stored {stored} headlines for {platform_id}")
        return stored
    
    def store_crawl_result(self, result: CrawlResult, save_json: bool = True) -> int:
        """
        Store a complete crawl result.
        
        Args:
            result: CrawlResult object
            save_json: Whether to also save JSON file
            
        Returns:
            Crawl session ID
        """
        crawl_date = result.crawl_time.strftime("%Y-%m-%d")
        total_headlines = sum(len(items) for items in result.platforms.values())
        
        # Create crawl session
        with self.db.connection() as conn:
            cursor = conn.execute("""
                INSERT INTO crawl_sessions 
                (crawl_time, crawl_date, timezone, version, total_platforms, failed_platforms, total_headlines)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                result.crawl_time,
                crawl_date,
                result.timezone,
                result.version,
                len(result.platforms),
                len(result.failed_platforms),
                total_headlines
            ))
            session_id = cursor.lastrowid
        
        # Store headlines for each platform
        for platform_id, items in result.platforms.items():
            if items:
                platform_name = items[0].platform_name if items else platform_id
                self.store_headlines(
                    items,
                    platform_id,
                    platform_name,
                    result.crawl_time,
                    session_id
                )
                
                # Record platform stats
                with self.db.connection() as conn:
                    conn.execute("""
                        INSERT INTO platform_stats 
                        (crawl_session_id, platform_id, platform_name, language, item_count, success)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        session_id,
                        platform_id,
                        platform_name,
                        items[0].language if items else 'en',
                        len(items),
                        True
                    ))
        
        # Record failed platforms
        for platform_id in result.failed_platforms:
            with self.db.connection() as conn:
                conn.execute("""
                    INSERT INTO platform_stats 
                    (crawl_session_id, platform_id, success)
                    VALUES (?, ?, ?)
                """, (session_id, platform_id, False))
        
        # Save JSON file if requested
        if save_json:
            self._save_json(result, session_id)
        
        logger.info(f"Stored crawl session {session_id}: {total_headlines} headlines from {len(result.platforms)} platforms")
        return session_id
    
    def _save_json(self, result: CrawlResult, session_id: int):
        """Save crawl result to JSON file."""
        crawl_date = result.crawl_time.strftime("%Y-%m-%d")
        crawl_time_str = result.crawl_time.strftime("%H-%M")
        
        json_dir = self.output_dir / crawl_date / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        
        json_path = json_dir / f"{crawl_time_str}.json"
        
        # Build JSON structure
        data = {
            "metadata": {
                "crawl_time": result.crawl_time.isoformat(),
                "timezone": result.timezone,
                "version": result.version,
                "total_platforms": len(result.platforms),
                "failed_platforms": len(result.failed_platforms),
                "session_id": session_id
            },
            "platforms": {}
        }
        
        for platform_id, items in result.platforms.items():
            if items:
                data["platforms"][platform_id] = {
                    "name": items[0].platform_name,
                    "language": items[0].language,
                    "item_count": len(items),
                    "items": [item.to_dict() for item in items]
                }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Update session with file path
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE crawl_sessions SET json_file = ? WHERE id = ?",
                (str(json_path), session_id)
            )
        
        logger.debug(f"Saved JSON to {json_path}")
    
    # ========== Search ==========
    
    def search_headlines(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50
    ) -> List[dict]:
        """
        Full-text search across headlines.
        
        Args:
            query: Search query (supports FTS5 syntax)
            platforms: Optional list of platform IDs to filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            limit: Maximum results
            
        Returns:
            List of matching headlines with URLs
        """
        with self.db.connection() as conn:
            # Build query
            sql = """
                SELECT 
                    h.id,
                    h.title,
                    h.platform_id,
                    h.platform_name,
                    h.rank,
                    h.language,
                    h.crawl_time,
                    h.crawl_date,
                    u.normalized_url as url,
                    u.domain,
                    bm25(headlines_fts) as relevance
                FROM headlines_fts
                JOIN headlines h ON headlines_fts.rowid = h.id
                LEFT JOIN urls u ON h.url_id = u.id
                WHERE headlines_fts MATCH ?
            """
            params = [query]
            
            if platforms:
                placeholders = ','.join('?' * len(platforms))
                sql += f" AND h.platform_id IN ({placeholders})"
                params.extend(platforms)
            
            if start_date:
                sql += " AND h.crawl_date >= ?"
                params.append(start_date)
            
            if end_date:
                sql += " AND h.crawl_date <= ?"
                params.append(end_date)
            
            sql += " ORDER BY relevance LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_headlines_by_date(
        self,
        date: str,
        platforms: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[dict]:
        """
        Get headlines for a specific date.
        
        Args:
            date: Date string (YYYY-MM-DD)
            platforms: Optional list of platform IDs
            limit: Maximum results
            
        Returns:
            List of headlines
        """
        with self.db.connection() as conn:
            sql = """
                SELECT 
                    h.*,
                    u.normalized_url as url,
                    u.domain
                FROM headlines h
                LEFT JOIN urls u ON h.url_id = u.id
                WHERE h.crawl_date = ?
            """
            params = [date]
            
            if platforms:
                placeholders = ','.join('?' * len(platforms))
                sql += f" AND h.platform_id IN ({placeholders})"
                params.extend(platforms)
            
            sql += " ORDER BY h.platform_id, h.rank LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_headlines(
        self,
        platforms: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[dict]:
        """
        Get the most recent headlines.
        
        Args:
            platforms: Optional list of platform IDs
            limit: Maximum results
            
        Returns:
            List of headlines
        """
        with self.db.connection() as conn:
            sql = """
                SELECT 
                    h.*,
                    u.normalized_url as url,
                    u.domain
                FROM headlines h
                LEFT JOIN urls u ON h.url_id = u.id
            """
            params = []
            
            if platforms:
                placeholders = ','.join('?' * len(platforms))
                sql += f" WHERE h.platform_id IN ({placeholders})"
                params.extend(platforms)
            
            sql += " ORDER BY h.crawl_time DESC, h.rank LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== Statistics ==========
    
    def get_platform_summary(self, date: Optional[str] = None) -> List[dict]:
        """Get headline counts by platform."""
        with self.db.connection() as conn:
            if date:
                cursor = conn.execute("""
                    SELECT 
                        platform_id,
                        platform_name,
                        language,
                        COUNT(*) as headline_count,
                        MAX(crawl_time) as last_crawl
                    FROM headlines
                    WHERE crawl_date = ?
                    GROUP BY platform_id
                    ORDER BY headline_count DESC
                """, (date,))
            else:
                cursor = conn.execute("""
                    SELECT 
                        platform_id,
                        platform_name,
                        language,
                        COUNT(*) as headline_count,
                        MAX(crawl_time) as last_crawl
                    FROM headlines
                    GROUP BY platform_id
                    ORDER BY headline_count DESC
                """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_crawl_history(self, days: int = 7) -> List[dict]:
        """Get recent crawl sessions."""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT *
                FROM crawl_sessions
                ORDER BY crawl_time DESC
                LIMIT ?
            """, (days * 24,))  # Assume hourly crawls
            return [dict(row) for row in cursor.fetchall()]


# Global store instance
_store: Optional[DataStore] = None


def get_data_store(db: Optional[Database] = None) -> DataStore:
    """Get the global DataStore instance."""
    global _store
    
    if _store is None:
        _store = DataStore(db)
    
    return _store


def reset_data_store():
    """Reset the global DataStore instance (for testing)."""
    global _store
    _store = None
