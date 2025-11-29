"""
Quick MCP Tools Test

Cycles through all MCP tools to verify they respond correctly.
Run with: uv run pytest tests/test_mcp_tools_quick.py -v
"""
import pytest
import requests
import json

# REST API endpoint
API_URL = "http://localhost:3334"

# Timeout for each tool call (seconds)
TOOL_TIMEOUT = 30


@pytest.fixture(scope="module")
def api_available():
    """Check if REST API is available"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code != 200:
            pytest.skip(f"REST API not healthy: {response.status_code}")
    except requests.exceptions.ConnectionError:
        pytest.skip("REST API not running at localhost:3334")


def call_tool(tool_name: str, arguments: dict = None) -> dict:
    """Call an MCP tool via REST API"""
    payload = {"arguments": arguments or {}}
    response = requests.post(
        f"{API_URL}/tools/{tool_name}",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=TOOL_TIMEOUT
    )
    return response.json()


class TestMCPToolsQuick:
    """Quick tests for all MCP tools"""

    def test_resolve_date_range(self, api_available):
        """Test resolve_date_range tool"""
        result = call_tool("resolve_date_range", {"query": "today"})
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        assert "result" in result
        data = result["result"]
        assert "start_date" in data or "dates" in data, f"Unexpected response: {data}"
        print(f"✓ resolve_date_range: {data}")

    def test_get_latest_news(self, api_available):
        """Test get_latest_news tool"""
        result = call_tool("get_latest_news", {"limit": 3})
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        assert "result" in result
        data = result["result"]
        assert "news" in data, f"Missing 'news' in response: {data.keys()}"
        assert isinstance(data["news"], list), f"'news' is not a list: {type(data['news'])}"
        print(f"✓ get_latest_news: {len(data['news'])} items")

    def test_get_latest_news_with_platform(self, api_available):
        """Test get_latest_news with specific platform"""
        result = call_tool("get_latest_news", {"platforms": ["spiegel"], "limit": 2})
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        data = result["result"]
        assert "news" in data
        # Check all items are from spiegel
        for item in data["news"]:
            assert item.get("platform") == "spiegel", f"Wrong platform: {item.get('platform')}"
        print(f"✓ get_latest_news (spiegel): {len(data['news'])} items")

    def test_get_trending_topics(self, api_available):
        """Test get_trending_topics tool"""
        result = call_tool("get_trending_topics", {"limit": 5})
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        assert "result" in result
        data = result["result"]
        # Should return topics or a message
        assert "topics" in data or "message" in data or isinstance(data, list), f"Unexpected: {data}"
        print(f"✓ get_trending_topics: {data}")

    def test_get_news_by_date(self, api_available):
        """Test get_news_by_date tool"""
        result = call_tool("get_news_by_date", {"date": "2025-11-29", "limit": 3})
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        assert "result" in result
        data = result["result"]
        assert "news" in data or "headlines" in data or isinstance(data, list), f"Unexpected: {data}"
        print(f"✓ get_news_by_date: {data}")

    def test_analyze_topic_trend(self, api_available):
        """Test analyze_topic_trend tool"""
        result = call_tool("analyze_topic_trend", {"topic": "AI", "days": 7})
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        assert "result" in result
        data = result["result"]
        print(f"✓ analyze_topic_trend: {type(data)}")

    def test_analyze_sentiment(self, api_available):
        """Test analyze_sentiment tool"""
        result = call_tool("analyze_sentiment", {
            "headlines": ["Great news for technology", "Crisis deepens in region"]
        })
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        assert "result" in result
        data = result["result"]
        print(f"✓ analyze_sentiment: {data}")

    def test_search_news(self, api_available):
        """Test search_news tool"""
        result = call_tool("search_news", {"query": "technology", "limit": 3})
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        assert "result" in result
        data = result["result"]
        print(f"✓ search_news: {data}")

    def test_generate_summary_report(self, api_available):
        """Test generate_summary_report tool"""
        result = call_tool("generate_summary_report", {"date": "2025-11-29"})
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        assert "result" in result
        data = result["result"]
        print(f"✓ generate_summary_report: {type(data)}")

    def test_get_woodchuck_pages(self, api_available):
        """Test get_woodchuck_pages tool"""
        result = call_tool("get_woodchuck_pages", {})
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        assert "result" in result
        data = result["result"]
        print(f"✓ get_woodchuck_pages: {type(data)}")

    def test_search_headlines_fts(self, api_available):
        """Test search_headlines_fts tool (FTS5 full-text search)"""
        result = call_tool("search_headlines_fts", {"query": "news", "limit": 3})
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        assert "result" in result
        data = result["result"]
        print(f"✓ search_headlines_fts: {data}")


class TestMCPToolsEdgeCases:
    """Edge case tests for MCP tools"""

    def test_get_latest_news_empty_platforms(self, api_available):
        """Test get_latest_news with empty platforms list"""
        result = call_tool("get_latest_news", {"platforms": [], "limit": 3})
        
        # Should either return all platforms or handle gracefully
        assert result.get("success") is True or result.get("error"), f"Unexpected: {result}"
        print(f"✓ get_latest_news (empty platforms): handled")

    def test_get_latest_news_invalid_platform(self, api_available):
        """Test get_latest_news with non-existent platform"""
        result = call_tool("get_latest_news", {"platforms": ["nonexistent_platform_xyz"], "limit": 3})
        
        # Should return empty or handle gracefully
        assert "result" in result or "error" in result
        print(f"✓ get_latest_news (invalid platform): handled")

    def test_search_news_empty_query(self, api_available):
        """Test search_news with empty query"""
        result = call_tool("search_news", {"query": "", "limit": 3})
        
        # Should handle gracefully
        assert "result" in result or "error" in result
        print(f"✓ search_news (empty query): handled")

    def test_resolve_date_range_complex(self, api_available):
        """Test resolve_date_range with complex expression"""
        result = call_tool("resolve_date_range", {"query": "last week"})
        
        assert result.get("success") is True, f"Failed: {result.get('error')}"
        print(f"✓ resolve_date_range (last week): {result.get('result')}")


if __name__ == "__main__":
    # Run quick manual test
    print("=" * 60)
    print("Quick MCP Tools Test")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        print(f"API Health: {response.status_code}")
    except Exception as e:
        print(f"API not available: {e}")
        exit(1)
    
    # Get list of tools
    tools_response = requests.get(f"{API_URL}/tools", timeout=5)
    tools = tools_response.json().get("tools", [])
    print(f"\nFound {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")
    
    print("\n" + "=" * 60)
    print("Testing each tool...")
    print("=" * 60)
    
    test_cases = [
        ("resolve_date_range", {"query": "today"}),
        ("get_latest_news", {"limit": 2}),
        ("get_trending_topics", {"limit": 3}),
        ("get_news_by_date", {"date": "2025-11-29", "limit": 2}),
        ("analyze_topic_trend", {"topic": "AI", "days": 3}),
        ("analyze_sentiment", {"headlines": ["Good news", "Bad news"]}),
        ("search_news", {"query": "tech", "limit": 2}),
        ("generate_summary_report", {"date": "2025-11-29"}),
        ("get_woodchuck_pages", {}),
        ("search_headlines_fts", {"query": "news", "limit": 2}),
    ]
    
    results = []
    for tool_name, args in test_cases:
        try:
            result = call_tool(tool_name, args)
            success = result.get("success", False)
            error = result.get("error")
            if success:
                results.append((tool_name, "✓ PASS", None))
                print(f"✓ {tool_name}: PASS")
            else:
                results.append((tool_name, "✗ FAIL", error))
                print(f"✗ {tool_name}: FAIL - {error}")
        except Exception as e:
            results.append((tool_name, "✗ ERROR", str(e)))
            print(f"✗ {tool_name}: ERROR - {e}")
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    passed = sum(1 for _, status, _ in results if "PASS" in status)
    failed = sum(1 for _, status, _ in results if "FAIL" in status or "ERROR" in status)
    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")
    
    if failed > 0:
        print("\nFailed tools:")
        for name, status, error in results:
            if "FAIL" in status or "ERROR" in status:
                print(f"  - {name}: {error}")
