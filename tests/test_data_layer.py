"""
Tests for SQLite data layer - schema, store, and search.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mcp_server.data.schema import Database, get_database, reset_database, SCHEMA_VERSION
from mcp_server.data.store import DataStore, HeadlineItem, CrawlResult, get_data_store, reset_data_store


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        db.initialize()
        yield db


@pytest.fixture
def temp_store(temp_db):
    """Create a temporary DataStore for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DataStore(db=temp_db, output_dir=Path(tmpdir))
        yield store


class TestDatabaseSchema:
    """Tests for database schema and initialization."""
    
    def test_database_initialization(self, temp_db):
        """Database should initialize successfully."""
        assert temp_db.db_path.exists()
    
    def test_schema_version(self, temp_db):
        """Schema version should be set."""
        version = temp_db.get_schema_version()
        assert version == SCHEMA_VERSION
    
    def test_tables_created(self, temp_db):
        """All tables should be created."""
        expected_tables = ['schema_info', 'urls', 'headlines', 'crawl_sessions', 'platform_stats']
        
        with temp_db.connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor.fetchall()]
        
        for table in expected_tables:
            assert table in tables, f"Table {table} not found"
    
    def test_fts_table_created(self, temp_db):
        """FTS5 virtual table should be created."""
        with temp_db.connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='headlines_fts'"
            )
            assert cursor.fetchone() is not None
    
    def test_indexes_created(self, temp_db):
        """Indexes should be created."""
        with temp_db.connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = [row[0] for row in cursor.fetchall()]
        
        assert 'idx_urls_hash' in indexes
        assert 'idx_headlines_platform' in indexes
    
    def test_stats_empty_db(self, temp_db):
        """Stats should work on empty database."""
        stats = temp_db.stats()
        assert stats['urls_count'] == 0
        assert stats['headlines_count'] == 0


class TestURLManagement:
    """Tests for URL registration and lookup."""
    
    def test_register_url(self, temp_store):
        """Should register a new URL."""
        url = "https://example.com/article?utm_source=test"
        url_id, url_hash, is_new = temp_store.register_url(url, source="test")
        
        assert url_id > 0
        assert len(url_hash) == 16
        assert is_new is True
    
    def test_register_duplicate_url(self, temp_store):
        """Should recognize duplicate URLs."""
        url = "https://example.com/article"
        
        _, hash1, new1 = temp_store.register_url(url, source="first")
        _, hash2, new2 = temp_store.register_url(url, source="second")
        
        assert hash1 == hash2
        assert new1 is True
        assert new2 is False
    
    def test_tracking_params_deduplication(self, temp_store):
        """URLs with different tracking params should deduplicate."""
        url1 = "https://example.com/page?id=123&utm_source=twitter"
        url2 = "https://example.com/page?id=123&fbclid=abc123"
        
        _, hash1, _ = temp_store.register_url(url1)
        _, hash2, new2 = temp_store.register_url(url2)
        
        assert hash1 == hash2
        assert new2 is False
    
    def test_lookup_url(self, temp_store):
        """Should find registered URL."""
        url = "https://example.com/test"
        temp_store.register_url(url, source="cached")
        
        result = temp_store.lookup_url(url)
        
        assert result is not None
        assert "cached" in result['source']
    
    def test_lookup_missing_url(self, temp_store):
        """Should return None for unregistered URL."""
        result = temp_store.lookup_url("https://notregistered.com/page")
        assert result is None
    
    def test_find_cached_url(self, temp_store):
        """Should find cached version of URL."""
        url = "https://example.com/cached-page"
        temp_store.register_url(url, source="cached")
        
        # Look up with tracking params
        cached = temp_store.find_cached_url(url + "?utm_source=search")
        
        assert cached is not None
        assert "utm_source" not in cached
    
    def test_get_urls_by_domain(self, temp_store):
        """Should get all URLs for a domain."""
        temp_store.register_url("https://example.com/page1")
        temp_store.register_url("https://example.com/page2")
        temp_store.register_url("https://other.com/page")
        
        results = temp_store.get_urls_by_domain("example.com")
        
        assert len(results) == 2


class TestHeadlineStorage:
    """Tests for headline storage and retrieval."""
    
    def test_store_headlines(self, temp_store):
        """Should store headlines."""
        headlines = [
            HeadlineItem(
                title="Test Headline 1",
                url="https://example.com/article1",
                platform_id="test",
                platform_name="Test Platform",
                rank=1
            ),
            HeadlineItem(
                title="Test Headline 2",
                url="https://example.com/article2",
                platform_id="test",
                platform_name="Test Platform",
                rank=2
            ),
        ]
        
        count = temp_store.store_headlines(
            headlines,
            platform_id="test",
            platform_name="Test Platform",
            crawl_time=datetime.now()
        )
        
        assert count == 2
    
    def test_store_crawl_result(self, temp_store):
        """Should store complete crawl result."""
        headlines = [
            HeadlineItem(
                title="Spiegel News",
                url="https://spiegel.de/article",
                platform_id="spiegel",
                platform_name="Der Spiegel",
                language="de"
            )
        ]
        
        result = CrawlResult(
            crawl_time=datetime.now(),
            platforms={"spiegel": headlines},
            timezone="Europe/Berlin",
            version="1.0.0"
        )
        
        session_id = temp_store.store_crawl_result(result, save_json=False)
        
        assert session_id > 0
    
    def test_get_headlines_by_date(self, temp_store):
        """Should retrieve headlines by date."""
        crawl_time = datetime.now()
        headlines = [
            HeadlineItem(
                title="Today's News",
                url="https://example.com/today",
                platform_id="test"
            )
        ]
        
        temp_store.store_headlines(
            headlines,
            platform_id="test",
            platform_name="Test",
            crawl_time=crawl_time
        )
        
        results = temp_store.get_headlines_by_date(crawl_time.strftime("%Y-%m-%d"))
        
        assert len(results) == 1
        assert results[0]['title'] == "Today's News"
    
    def test_get_latest_headlines(self, temp_store):
        """Should get most recent headlines."""
        headlines = [
            HeadlineItem(title="Latest News", url="https://example.com/1", platform_id="test")
        ]
        
        temp_store.store_headlines(headlines, "test", "Test", datetime.now())
        
        results = temp_store.get_latest_headlines(limit=10)
        
        assert len(results) >= 1


class TestFullTextSearch:
    """Tests for FTS5 full-text search."""
    
    def test_simple_search(self, temp_store):
        """Should find headlines by keyword."""
        headlines = [
            HeadlineItem(title="AI revolution in tech industry", url="https://a.com/1", platform_id="test"),
            HeadlineItem(title="Weather forecast for tomorrow", url="https://a.com/2", platform_id="test"),
            HeadlineItem(title="Artificial Intelligence news", url="https://a.com/3", platform_id="test"),
        ]
        
        temp_store.store_headlines(headlines, "test", "Test", datetime.now())
        
        results = temp_store.search_headlines("AI")
        
        assert len(results) >= 1
        assert any("AI" in r['title'] for r in results)
    
    def test_phrase_search(self, temp_store):
        """Should find exact phrases."""
        headlines = [
            HeadlineItem(title="The quick brown fox", url="https://a.com/1", platform_id="test"),
            HeadlineItem(title="Quick fox jumps", url="https://a.com/2", platform_id="test"),
        ]
        
        temp_store.store_headlines(headlines, "test", "Test", datetime.now())
        
        results = temp_store.search_headlines('"quick brown"')
        
        assert len(results) == 1
        assert "quick brown" in results[0]['title'].lower()
    
    def test_search_with_platform_filter(self, temp_store):
        """Should filter by platform."""
        temp_store.store_headlines(
            [HeadlineItem(title="Tech news A", url="https://a.com/1", platform_id="tech")],
            "tech", "Tech News", datetime.now()
        )
        temp_store.store_headlines(
            [HeadlineItem(title="Tech news B", url="https://b.com/1", platform_id="sports")],
            "sports", "Sports News", datetime.now()
        )
        
        results = temp_store.search_headlines("Tech", platforms=["tech"])
        
        assert all(r['platform_id'] == "tech" for r in results)
    
    def test_search_with_date_range(self, temp_store):
        """Should filter by date range."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        temp_store.store_headlines(
            [HeadlineItem(title="Today news", url="https://a.com/1", platform_id="test")],
            "test", "Test", datetime.now()
        )
        
        results = temp_store.search_headlines("news", start_date=today, end_date=today)
        
        assert len(results) >= 1


class TestPlatformStats:
    """Tests for platform statistics."""
    
    def test_get_platform_summary(self, temp_store):
        """Should get headline counts by platform."""
        for i in range(5):
            temp_store.store_headlines(
                [HeadlineItem(title=f"News {i}", url=f"https://a.com/{i}", platform_id="platform_a")],
                "platform_a", "Platform A", datetime.now()
            )
        
        for i in range(3):
            temp_store.store_headlines(
                [HeadlineItem(title=f"News {i}", url=f"https://b.com/{i}", platform_id="platform_b")],
                "platform_b", "Platform B", datetime.now()
            )
        
        summary = temp_store.get_platform_summary()
        
        assert len(summary) == 2
        assert any(p['platform_id'] == 'platform_a' and p['headline_count'] == 5 for p in summary)
    
    def test_crawl_history(self, temp_store):
        """Should return crawl history."""
        result = CrawlResult(
            crawl_time=datetime.now(),
            platforms={"test": []},
            version="1.0.0"
        )
        
        temp_store.store_crawl_result(result, save_json=False)
        
        history = temp_store.get_crawl_history(days=1)
        
        assert len(history) >= 1


class TestGlobalInstances:
    """Tests for global singleton instances."""
    
    def test_reset_database(self):
        """Should reset global database instance."""
        reset_database()
        db1 = get_database()
        reset_database()
        db2 = get_database()
        
        # Should be different instances
        assert db1 is not db2
    
    def test_reset_data_store(self):
        """Should reset global data store instance."""
        reset_data_store()
        store1 = get_data_store()
        reset_data_store()
        store2 = get_data_store()
        
        assert store1 is not store2


# Timeout for all tests
pytestmark = pytest.mark.timeout(10)
