#!/usr/bin/env python3
"""Test meta search functionality"""

import json
import sys
sys.path.insert(0, '.')

from mcp_server.services.search_service import MetaSearchService, SiteSearchService

# First test just site search to ensure it works
print("=== Testing SiteSearchService directly ===")
site_search = SiteSearchService()

# Test Guardian (API-based, should be fast and reliable)
print("Testing theguardian...")
guardian_results = site_search.search("theguardian", "climate", max_results=5)
print(f"Guardian results: {len(guardian_results)}")
for r in guardian_results[:2]:
    print(f"  - {r.get('title', 'N/A')[:50]}...")

print()

# Test Folha (cloudscraper-based)
print("Testing folha (cloudscraper)...")
folha_results = site_search.search("folha", "brasil", max_results=5)
print(f"Folha results: {len(folha_results)}")
for r in folha_results[:2]:
    print(f"  - {r.get('title', 'N/A')[:50]}...")

print()
print("=== Testing MetaSearchService ===")
service = MetaSearchService()

result = service.research_topic(
    topic="climate",
    languages=["en"],
    max_results_per_query=10
)

print(f"Success: {result.get('success')}")
print(f"Total articles: {result.get('total_articles')}")
print(f"Clusters: {result.get('cluster_count')}")
print(f"Time: {result.get('search_time_seconds')}s")
print()
print("Key stories:")
for story in result.get('key_stories', [])[:5]:
    print(f"  - [{story['platform']}] {story['title'][:45]}...")
print()
print("Platform coverage:")
for platform, data in result.get('platform_coverage', {}).items():
    print(f"  {platform}: {data['count']} articles")
