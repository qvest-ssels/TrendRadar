# Data Layer TODOs

## Completed
- [x] SQLite schema with FTS5 full-text search
- [x] DataStore unified access layer (dual-write SQLite + JSON)
- [x] URL registry with deduplication and tracking param removal
- [x] Migration script for importing existing JSON files
- [x] Data layer tests (25 tests passing)

## In Progress
- [ ] Integrate DataStore with main.py crawler
  - Replace direct file writes with DataStore.store_crawl_result()
  - Maintain backward compatibility with JSON output

## Future
- [ ] Add URL cache interlinking
  - When live search finds a URL, check if it exists in cache
  - Return cached metadata alongside live results
- [ ] Add statistics dashboard
  - Track crawl frequency, platform reliability
  - URL discovery rate over time
- [ ] Database maintenance
  - Auto-vacuum on schedule
  - Prune old data (configurable retention)
- [ ] Performance optimization
  - Connection pooling for high concurrency
  - Batch inserts for large crawls

## Schema Changes (requires migration)
- None pending

## Notes
- Database location: `output/trendradar.db`
- Uses WAL mode for better concurrent access
- FTS5 for full-text search on headlines
- 100+ tracking parameters stripped from URLs
