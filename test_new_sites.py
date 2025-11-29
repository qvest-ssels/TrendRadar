#!/usr/bin/env python3
"""Test new sites for RSS and search"""

import sys
sys.path.insert(0, '.')
from main import DataFetcher
import json

fetcher = DataFetcher(debug_mode=True)

# Test Japan Times (no cloudflare)
print("=== Testing Japan Times ===")
japan_config = {
    "id": "japantimes",
    "name": "The Japan Times",
    "crawler": {
        "type": "rss",
        "url_template": "https://www.japantimes.co.jp/feed/"
    }
}
result, id_val, alias = fetcher.fetch_data(japan_config)
if result:
    data = json.loads(result)
    print(f"Items: {len(data.get('items', []))}")
    if data.get("items"):
        print(f"First: {data['items'][0]['title'][:50]}")

print()

# Test Korea Herald (with cloudflare + sub-feeds)
print("=== Testing Korea Herald (cloudflare + sub-feeds) ===")
korea_config = {
    "id": "koreaherald",
    "name": "The Korea Herald",
    "cdn": "cloudflare",
    "crawler": {
        "type": "rss",
        "url_template": "https://www.koreaherald.com/rss/kh_National",
        "sub_feeds": [
            {"name": "Business", "url": "https://www.koreaherald.com/rss/kh_Business"},
            {"name": "World", "url": "https://www.koreaherald.com/rss/kh_World"},
        ]
    }
}
result, id_val, alias = fetcher.fetch_data(korea_config)
if result:
    data = json.loads(result)
    print(f"Total unique items: {len(data.get('items', []))}")
    if data.get("items"):
        print(f"First: {data['items'][0]['title'][:50]}")
