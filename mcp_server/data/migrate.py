#!/usr/bin/env python3
"""
Migration script to import existing JSON files into SQLite database.

Usage:
    python -m mcp_server.data.migrate [--output-dir OUTPUT_DIR] [--db-path DB_PATH]
    
This script scans the output directory for existing JSON crawl files
and imports them into the SQLite database for full-text search.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp_server.data.schema import Database, DEFAULT_DB_PATH
from mcp_server.data.store import DataStore, HeadlineItem, CrawlResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def find_json_files(output_dir: Path) -> list[Path]:
    """Find all JSON crawl files in the output directory."""
    json_files = []
    
    for date_dir in sorted(output_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        
        json_dir = date_dir / "json"
        if json_dir.exists():
            for json_file in sorted(json_dir.glob("*.json")):
                json_files.append(json_file)
    
    return json_files


def parse_crawl_file(json_path: Path) -> Optional[CrawlResult]:
    """Parse a JSON crawl file into a CrawlResult."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to read {json_path}: {e}")
        return None
    
    metadata = data.get('metadata', {})
    platforms_data = data.get('platforms', {})
    
    # Parse crawl time
    crawl_time_str = metadata.get('crawl_time', '')
    try:
        crawl_time = datetime.fromisoformat(crawl_time_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        # Fall back to file modification time
        crawl_time = datetime.fromtimestamp(json_path.stat().st_mtime)
    
    # Parse platforms
    platforms = {}
    for platform_id, platform_data in platforms_data.items():
        items = []
        for item in platform_data.get('items', []):
            headline = HeadlineItem(
                title=item.get('title', ''),
                url=item.get('url', ''),
                platform_id=platform_id,
                platform_name=platform_data.get('name', platform_id),
                rank=item.get('rank', 0),
                language=platform_data.get('language', 'en'),
                mobile_url=item.get('mobile_url', '')
            )
            items.append(headline)
        
        if items:
            platforms[platform_id] = items
    
    return CrawlResult(
        crawl_time=crawl_time,
        platforms=platforms,
        timezone=metadata.get('timezone', 'UTC'),
        version=metadata.get('version', ''),
        failed_platforms=[]
    )


def migrate(
    output_dir: Path,
    db_path: Optional[Path] = None,
    dry_run: bool = False,
    skip_existing: bool = True
):
    """
    Migrate JSON files to SQLite database.
    
    Args:
        output_dir: Directory containing JSON crawl files
        db_path: Path to SQLite database
        dry_run: If True, only show what would be migrated
        skip_existing: If True, skip files already in database
    """
    # Initialize database
    db = Database(db_path or DEFAULT_DB_PATH)
    db.initialize()
    
    store = DataStore(db=db, output_dir=output_dir)
    
    # Find JSON files
    json_files = find_json_files(output_dir)
    logger.info(f"Found {len(json_files)} JSON files to migrate")
    
    if not json_files:
        logger.info("No files to migrate")
        return
    
    if dry_run:
        logger.info("Dry run - no changes will be made")
        for f in json_files:
            logger.info(f"  Would import: {f}")
        return
    
    # Track progress
    imported = 0
    skipped = 0
    failed = 0
    total_headlines = 0
    
    for json_path in json_files:
        logger.info(f"Processing: {json_path}")
        
        # Check if already imported
        if skip_existing:
            with db.connection() as conn:
                cursor = conn.execute(
                    "SELECT id FROM crawl_sessions WHERE json_file = ?",
                    (str(json_path),)
                )
                if cursor.fetchone():
                    logger.debug(f"  Skipping (already imported)")
                    skipped += 1
                    continue
        
        # Parse and import
        result = parse_crawl_file(json_path)
        if result is None:
            failed += 1
            continue
        
        if not result.platforms:
            logger.warning(f"  No platforms in {json_path}")
            skipped += 1
            continue
        
        try:
            # Store in database (don't re-save JSON)
            session_id = store.store_crawl_result(result, save_json=False)
            
            # Update session with file reference
            with db.connection() as conn:
                conn.execute(
                    "UPDATE crawl_sessions SET json_file = ? WHERE id = ?",
                    (str(json_path), session_id)
                )
            
            headline_count = sum(len(items) for items in result.platforms.values())
            total_headlines += headline_count
            imported += 1
            logger.info(f"  Imported {headline_count} headlines from {len(result.platforms)} platforms")
            
        except Exception as e:
            logger.error(f"  Failed to import: {e}")
            failed += 1
    
    # Summary
    logger.info("=" * 50)
    logger.info("Migration complete!")
    logger.info(f"  Imported: {imported} files ({total_headlines} headlines)")
    logger.info(f"  Skipped: {skipped} files")
    logger.info(f"  Failed: {failed} files")
    
    # Show database stats
    stats = db.stats()
    logger.info("Database statistics:")
    logger.info(f"  Total URLs: {stats['urls_count']}")
    logger.info(f"  Total headlines: {stats['headlines_count']}")
    logger.info(f"  Total crawl sessions: {stats['crawl_sessions_count']}")
    logger.info(f"  Database size: {stats['db_size_mb']} MB")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate existing JSON crawl files to SQLite database"
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path(__file__).parent.parent.parent / 'output',
        help='Output directory containing JSON files (default: output/)'
    )
    parser.add_argument(
        '--db-path',
        type=Path,
        default=None,
        help='Path to SQLite database (default: output/trendradar.db)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without making changes'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Re-import all files, even if already in database'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if not args.output_dir.exists():
        logger.error(f"Output directory does not exist: {args.output_dir}")
        sys.exit(1)
    
    migrate(
        output_dir=args.output_dir,
        db_path=args.db_path,
        dry_run=args.dry_run,
        skip_existing=not args.force
    )


if __name__ == '__main__':
    main()
