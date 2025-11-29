#!/usr/bin/env python3
"""Test script for cloudscraper Cloudflare bypass."""

import asyncio
import sys
sys.path.insert(0, '/Users/ssels/workspace/ranD/TrendRadar')

from mcp_server.services.cloudscraper_service import get_cloudscraper_service


async def test_cloudflare_sites():
    """Test cloudscraper against Cloudflare-protected news sites."""
    
    service = get_cloudscraper_service()
    
    # Cloudflare-protected sites from our config
    test_sites = [
        ('folha', 'https://www.folha.uol.com.br/', 'Portuguese'),
        ('timesofisrael', 'https://www.timesofisrael.com/', 'English'),
        ('dailymaverick', 'https://www.dailymaverick.co.za/', 'English'),
        ('aawsat', 'https://english.aawsat.com/', 'English/Arabic'),
    ]
    
    print("=" * 70)
    print("Testing Cloudscraper Cloudflare Bypass")
    print("=" * 70)
    
    results = []
    
    for platform_id, url, language in test_sites:
        print(f"\n🔍 Testing {platform_id} ({language})")
        print(f"   URL: {url}")
        
        result = await service.test_cloudflare_bypass(url)
        results.append((platform_id, result))
        
        if result['success']:
            print(f"   ✅ SUCCESS: {result['message']}")
            print(f"   📄 Title: {result.get('title', 'N/A')}")
            print(f"   📰 Has articles: {result.get('has_articles', 'N/A')}")
            print(f"   📊 Content length: {result['content_length']} chars")
        else:
            status = "🚫 BLOCKED" if result['blocked'] else "❌ FAILED"
            print(f"   {status}: {result['message']}")
    
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    success_count = sum(1 for _, r in results if r['success'])
    print(f"\n✅ Successful: {success_count}/{len(results)}")
    
    for platform_id, result in results:
        status = "✅" if result['success'] else "❌"
        print(f"   {status} {platform_id}")
    
    service.close()
    return results


async def test_folha_search():
    """Test search on Folha."""
    
    service = get_cloudscraper_service()
    
    print("\n" + "=" * 70)
    print("Testing Folha Search")
    print("=" * 70)
    
    # Folha search URL format
    search_url = "https://search.folha.uol.com.br/?q={query}&site=todos"
    
    results = await service.search_site(
        search_url=search_url,
        query="economia",
        result_selector='.c-headline',
        title_selector='a',
        link_selector='a',
        max_results=5
    )
    
    if results:
        print(f"\n✅ Found {len(results)} results:")
        for i, r in enumerate(results, 1):
            print(f"   {i}. {r['title'][:60]}...")
            print(f"      {r['url']}")
    else:
        print("\n❌ No results found")
    
    service.close()
    return results


if __name__ == '__main__':
    # Run tests
    asyncio.run(test_cloudflare_sites())
    asyncio.run(test_folha_search())
