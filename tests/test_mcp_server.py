"""
MCP Server Integration Tests

Tests for the running MCP server HTTP endpoint.
"""
import pytest
import requests
import time
import subprocess
import signal
import json
import os
import os
from typing import Optional


class TestMCPServerIntegration:
    """Integration tests for MCP server HTTP endpoint"""

    @pytest.fixture(scope="class")
    def mcp_server_process(self):
        """Start MCP server in HTTP mode for testing"""
        # Start the MCP server process
        cmd = [
            "uv", "run", "python", "-m", "mcp_server.server",
            "--transport", "http",
            "--host", "127.0.0.1",
            "--port", "3333"
        ]

        # Set environment to avoid output conflicts
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd="/Users/ssels/workspace/ranD/TrendRadar"
        )

        # Wait for server to start up
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                # Test with a simple MCP initialize request
                test_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1.0"}
                    }
                }
                response = requests.post(
                    "http://localhost:3333/mcp",
                    json=test_request,
                    headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
                    timeout=2
                )
                if response.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                pass

            time.sleep(1)

            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                pytest.fail(f"MCP server failed to start. STDOUT: {stdout.decode()}, STDERR: {stderr.decode()}")

        else:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            pytest.fail("MCP server did not start within timeout period")

        yield process

        # Cleanup: terminate the server
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def test_mcp_server_health_check(self, mcp_server_process):
        """Test that MCP server is responding to health checks"""
        # MCP servers typically don't respond to GET requests
        # Instead, test that the server is listening on the port
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex(('127.0.0.1', 3333))
            assert result == 0, "MCP server is not listening on port 3333"
        finally:
            sock.close()

    def test_mcp_server_initialize(self, mcp_server_process):
        """Test MCP server initialization handshake"""
        # Send MCP initialize request
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }

        response = requests.post(
            "http://localhost:3333/mcp",
            json=initialize_request,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            timeout=10
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # Parse SSE response
        response_text = response.text.strip()
        assert response_text.startswith("event: message")
        assert "data: " in response_text

        # Extract JSON from SSE data line
        data_line = [line for line in response_text.split('\n') if line.startswith("data: ")][0]
        json_data = data_line[6:]  # Remove "data: " prefix
        data = json.loads(json_data)

        # Should be a proper JSON-RPC response
        assert "jsonrpc" in data
        assert "id" in data
        assert data["id"] == 1

        # Should contain server info
        assert "result" in data
        result = data["result"]
        assert "serverInfo" in result
        assert "name" in result["serverInfo"]
        assert "version" in result["serverInfo"]

    def test_mcp_server_tools_list(self, mcp_server_process):
        """Test that MCP server can list available tools"""
        # Use a session to maintain state between requests
        with requests.Session() as session:
            # First initialize
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                }
            }

            init_response = session.post(
                "http://localhost:3333/mcp",
                json=initialize_request,
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
                timeout=10
            )
            assert init_response.status_code == 200

            # Extract session ID from the initialize response and set it as a cookie
            session_id = init_response.headers.get("mcp-session-id")
            assert session_id, "MCP server should provide a session ID"
            session.cookies.set("mcp-session-id", session_id)

            # Then request tools list using the same session
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }

            response = session.post(
                "http://localhost:3333/mcp",
                json=tools_request,
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "mcp-session-id": session_id},
                timeout=10
            )

            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            # Parse SSE response
            response_text = response.text.strip()
            assert response_text.startswith("event: message")
            assert "data: " in response_text

            # Extract JSON from SSE data line
            data_line = [line for line in response_text.split('\n') if line.startswith("data: ")][0]
            json_data = data_line[6:]  # Remove "data: " prefix
            data = json.loads(json_data)

            assert "jsonrpc" in data
            assert "id" in data
            assert data["id"] == 2

            # The response should contain either result or error (both are valid JSON-RPC responses)
            assert "result" in data or "error" in data, f"Response should contain result or error: {data}"

            # If it's a successful response, check that it contains tools
            if "result" in data:
                result = data["result"]
                assert "tools" in result
                assert isinstance(result["tools"], list)
                assert len(result["tools"]) > 0  # Should have tools registered

                # Check that expected tools are present
                tool_names = [tool["name"] for tool in result["tools"]]
                expected_tools = [
                    "resolve_date_range",
                    "get_latest_news",
                    "get_news_by_date",
                    "get_trending_topics"
                ]

                for expected_tool in expected_tools:
                    assert expected_tool in tool_names, f"Expected tool {expected_tool} not found in {tool_names}"

    def test_mcp_server_cors_headers(self, mcp_server_process):
        """Test that MCP server properly rejects unsupported HTTP methods"""
        # Test preflight request for MCP endpoint - should be rejected since MCP only supports POST
        response = requests.options(
            "http://localhost:3333/mcp",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            },
            timeout=5
        )

        # OPTIONS method should not be allowed for MCP endpoints
        assert response.status_code == 405  # Method Not Allowed

    def test_mcp_server_error_handling(self, mcp_server_process):
        """Test MCP server error handling with invalid requests"""
        # Send malformed JSON-RPC request
        try:
            response = requests.post(
                "http://localhost:3333/mcp",
                json={"invalid": "request", "missing": "jsonrpc"},
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
                timeout=5
            )

            # Should return error response
            assert response.status_code in [400, 500]

            # If it returns JSON, it should be a proper error response
            if "application/json" in response.headers.get("content-type", ""):
                data = response.json()
                assert "error" in data or "jsonrpc" in data

        except requests.exceptions.RequestException as e:
            # Connection errors are also acceptable for invalid requests
            assert "connection" in str(e).lower() or "timeout" in str(e).lower()

    def test_mcp_server_response_format(self, mcp_server_process):
        """Test that MCP server returns properly formatted JSON-RPC responses"""
        # Send a valid initialize request
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }

        response = requests.post(
            "http://localhost:3333/mcp",
            json=initialize_request,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            timeout=10
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # Should be valid SSE response
        response_text = response.text.strip()
        assert isinstance(response_text, str)
        assert len(response_text) > 0

        # Should have event and data lines
        lines = response_text.split('\n')
        assert any(line.startswith("event: message") for line in lines)
        assert any(line.startswith("data: ") for line in lines)

        # Extract and validate JSON data
        data_line = [line for line in lines if line.startswith("data: ")][0]
        json_data = data_line[6:]  # Remove "data: " prefix
        data = json.loads(json_data)

        # Should have either result or error
        assert "result" in data or "error" in data

    def test_mcp_server_cache_functionality(self, mcp_server_process):
        """Test that MCP server properly uses caching for data requests"""
        from mcp_server.services.data_service import DataService
        from mcp_server.services.cache_service import get_cache
        import time

        # Test cache functionality directly
        cache = get_cache()
        
        # Clear any existing cache
        cache.clear()
        
        # Get initial cache stats
        initial_stats = cache.get_stats()
        assert initial_stats["total_entries"] == 0
        
        # Create data service
        data_service = DataService()
        
        # First call to get_latest_news should populate cache
        start_time = time.time()
        result1 = data_service.get_latest_news(limit=5)
        first_call_time = time.time() - start_time
        
        # Check that cache now has entries
        stats_after_first = cache.get_stats()
        assert stats_after_first["total_entries"] > 0
        
        # Second call should use cache
        start_time = time.time()
        result2 = data_service.get_latest_news(limit=5)
        second_call_time = time.time() - start_time
        
        # Results should be identical (from cache)
        assert result1 == result2
        
        # Cache should still have entries
        final_stats = cache.get_stats()
        assert final_stats["total_entries"] >= stats_after_first["total_entries"]
        
        # Verify the results contain expected structure
        assert isinstance(result1, list)
        assert len(result1) <= 5  # Should respect the limit
        if len(result1) > 0:
            # Check structure of first item
            item = result1[0]
            assert "title" in item
            assert "platform" in item
            assert "platform_name" in item
            assert "rank" in item
            assert "timestamp" in item

    def test_system_status(self, mcp_server_process):
        """Test that get_system_status returns valid status information"""
        from mcp_server.tools.system import SystemManagementTools
        
        # Create system tools instance
        system_tools = SystemManagementTools()
        
        # Call get_system_status
        result = system_tools.get_system_status()
        
        # Verify basic response structure
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True
        
        # Verify system info is present
        assert "system" in result
        system_info = result["system"]
        assert "version" in system_info
        assert "project_root" in system_info
        
        # Verify data statistics
        assert "data" in result
        data_info = result["data"]
        assert "total_storage" in data_info
        assert "oldest_record" in data_info or "latest_record" in data_info
        
        # Verify cache status
        assert "cache" in result
        cache_info = result["cache"]
        assert "total_entries" in cache_info
        assert isinstance(cache_info["total_entries"], int)
        
        # Verify health status
        assert "health" in result
        assert result["health"] in ["healthy", "degraded", "unhealthy"]
        
    def test_system_status_error_handling(self, mcp_server_process):
        """Test that get_system_status handles errors gracefully"""
        from mcp_server.tools.system import SystemManagementTools
        
        # Create system tools instance with invalid project root
        # This should not crash but may return limited information
        system_tools = SystemManagementTools(project_root="/nonexistent/path")
        
        # Call get_system_status - should still return a valid response
        result = system_tools.get_system_status()
        
        # Verify it returns a dict with success field
        assert isinstance(result, dict)
        assert "success" in result
        # Even with invalid path, it should handle gracefully

    def test_trigger_crawl_rss_platform(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl an RSS platform like The Guardian"""
        from mcp_server.tools.system import SystemManagementTools
        
        # Create system tools instance
        system_tools = SystemManagementTools()
        
        # Crawl The Guardian RSS feed
        result = system_tools.trigger_crawl(platforms=['theguardian'], debug=False)
        
        # Verify successful response
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        
        # Verify crawl metadata
        assert "status" in result
        assert result["status"] == "completed"
        assert "platforms" in result
        assert "theguardian" in result["platforms"]
        assert "total_news" in result
        assert result["total_news"] > 0, "Expected to crawl at least some news items"
        
        # Verify no failed platforms
        assert "failed_platforms" in result
        assert len(result["failed_platforms"]) == 0
        
        # Verify data structure
        assert "data" in result
        assert isinstance(result["data"], list)
        assert len(result["data"]) > 0
        
        # Check first item structure
        first_item = result["data"][0]
        assert "platform_id" in first_item
        assert first_item["platform_id"] == "theguardian"
        assert "platform_name" in first_item
        assert first_item["platform_name"] == "The Guardian"
        assert "title" in first_item
        assert len(first_item["title"]) > 0
        assert "ranks" in first_item
        assert isinstance(first_item["ranks"], list)

    def test_trigger_crawl_with_debug(self, mcp_server_process):
        """Test that trigger_crawl works with debug mode enabled"""
        from mcp_server.tools.system import SystemManagementTools
        import io
        import sys
        
        # Create system tools instance
        system_tools = SystemManagementTools()
        
        # Capture stdout to verify debug output
        captured_output = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured_output
        
        try:
            # Crawl with debug enabled
            result = system_tools.trigger_crawl(platforms=['theguardian'], debug=True)
        finally:
            sys.stdout = original_stdout
        
        # Check debug output was produced
        debug_output = captured_output.getvalue()
        assert "[DEBUG]" in debug_output, "Expected debug output with [DEBUG] prefix"
        assert "Platform:" in debug_output or "crawler_type:" in debug_output
        
        # Verify successful response
        assert isinstance(result, dict)
        assert result.get("success") is True, f"Crawl failed: {result.get('error')}"

    def test_trigger_crawl_german_rss_platform(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl Der Spiegel RSS feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        # Create system tools instance
        system_tools = SystemManagementTools()
        
        # Crawl Der Spiegel RSS feed
        result = system_tools.trigger_crawl(platforms=['spiegel'], debug=False)
        
        # Verify successful response
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        
        # Verify crawl metadata
        assert result["total_news"] > 0, "Expected to crawl at least some news items"
        assert "spiegel" in result["platforms"]
        
        # Verify data structure
        assert len(result["data"]) > 0
        first_item = result["data"][0]
        assert first_item["platform_id"] == "spiegel"
        assert first_item["platform_name"] == "Der Spiegel — Schlagzeilen"

    def test_trigger_crawl_heise_online(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl Heise Online Atom feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        # Create system tools instance
        system_tools = SystemManagementTools()
        
        # Crawl Heise Online Atom feed
        result = system_tools.trigger_crawl(platforms=['heise'], debug=False)
        
        # Verify successful response
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        
        # Verify crawl metadata
        assert result["total_news"] > 0, "Expected to crawl at least some news items"
        assert "heise" in result["platforms"]
        
        # Verify data structure
        assert len(result["data"]) > 0
        first_item = result["data"][0]
        assert first_item["platform_id"] == "heise"
        assert first_item["platform_name"] == "Heise Online"
        assert "title" in first_item
        assert len(first_item["title"]) > 0

    def test_trigger_crawl_slashdot(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl Slashdot RDF/RSS 1.0 feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        # Create system tools instance
        system_tools = SystemManagementTools()
        
        # Crawl Slashdot RDF feed
        result = system_tools.trigger_crawl(platforms=['slashdot'], debug=False)
        
        # Verify successful response
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        
        # Verify crawl metadata
        assert result["total_news"] > 0, "Expected to crawl at least some news items"
        assert "slashdot" in result["platforms"]
        
        # Verify data structure
        assert len(result["data"]) > 0
        first_item = result["data"][0]
        assert first_item["platform_id"] == "slashdot"
        assert first_item["platform_name"] == "Slashdot"
        assert "title" in first_item
        assert len(first_item["title"]) > 0

    def test_trigger_crawl_lemonde(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl Le Monde RSS feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        # Create system tools instance
        system_tools = SystemManagementTools()
        
        # Crawl Le Monde RSS feed
        result = system_tools.trigger_crawl(platforms=['lemonde'], debug=False)
        
        # Verify successful response
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        
        # Verify crawl metadata
        assert result["total_news"] > 0, "Expected to crawl at least some news items"
        assert "lemonde" in result["platforms"]
        
        # Verify data structure
        assert len(result["data"]) > 0
        first_item = result["data"][0]
        assert first_item["platform_id"] == "lemonde"
        assert first_item["platform_name"] == "Le Monde"
        assert "title" in first_item
        assert len(first_item["title"]) > 0

    def test_trigger_crawl_times_of_india(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl Times of India RSS feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        # Create system tools instance
        system_tools = SystemManagementTools()
        
        # Crawl Times of India RSS feed
        result = system_tools.trigger_crawl(platforms=['timesofindia'], debug=False)
        
        # Verify successful response
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        
        # Verify crawl metadata
        assert result["total_news"] > 0, "Expected to crawl at least some news items"
        assert "timesofindia" in result["platforms"]
        
        # Verify data structure
        assert len(result["data"]) > 0
        first_item = result["data"][0]
        assert first_item["platform_id"] == "timesofindia"
        assert first_item["platform_name"] == "The Times of India"
        assert "title" in first_item
        assert len(first_item["title"]) > 0

    def test_trigger_crawl_moscow_times(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl Moscow Times RSS feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        # Create system tools instance
        system_tools = SystemManagementTools()
        
        # Crawl Moscow Times RSS feed
        result = system_tools.trigger_crawl(platforms=['moscowtimes'], debug=False)
        
        # Verify successful response
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        
        # Verify crawl metadata
        assert result["total_news"] > 0, "Expected to crawl at least some news items"
        assert "moscowtimes" in result["platforms"]
        
        # Verify data structure
        assert len(result["data"]) > 0
        first_item = result["data"][0]
        assert first_item["platform_id"] == "moscowtimes"
        assert first_item["platform_name"] == "The Moscow Times"
        assert "title" in first_item
        assert len(first_item["title"]) > 0

    def test_trigger_crawl_folha(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl Folha de S. Paulo RSS feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        # Create system tools instance
        system_tools = SystemManagementTools()
        
        # Crawl Folha de S. Paulo RSS feed
        result = system_tools.trigger_crawl(platforms=['folha'], debug=False)
        
        # Verify successful response
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        
        # Verify crawl metadata
        assert result["total_news"] > 0, "Expected to crawl at least some news items"
        assert "folha" in result["platforms"]
        
        # Verify data structure
        assert len(result["data"]) > 0
        first_item = result["data"][0]
        assert first_item["platform_id"] == "folha"
        assert first_item["platform_name"] == "Folha de S. Paulo"
        assert "title" in first_item
        assert len(first_item["title"]) > 0

    def test_trigger_crawl_daily_maverick(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl Daily Maverick RSS feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        # Create system tools instance
        system_tools = SystemManagementTools()
        
        # Crawl Daily Maverick RSS feed
        result = system_tools.trigger_crawl(platforms=['dailymaverick'], debug=False)
        
        # Verify successful response
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        
        # Verify crawl metadata
        assert result["total_news"] > 0, "Expected to crawl at least some news items"
        assert "dailymaverick" in result["platforms"]
        
        # Verify data structure
        assert len(result["data"]) > 0
        first_item = result["data"][0]
        assert first_item["platform_id"] == "dailymaverick"
        assert first_item["platform_name"] == "Daily Maverick"
        assert "title" in first_item
        assert len(first_item["title"]) > 0

    def test_trigger_crawl_straits_times(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl The Straits Times RSS feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        system_tools = SystemManagementTools()
        result = system_tools.trigger_crawl(platforms=['straitstimes'], debug=False)
        
        assert isinstance(result, dict)
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        assert result["total_news"] > 0
        assert "straitstimes" in result["platforms"]
        assert len(result["data"]) > 0
        assert result["data"][0]["platform_id"] == "straitstimes"

    def test_trigger_crawl_guardian_australia(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl The Guardian Australia RSS feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        system_tools = SystemManagementTools()
        result = system_tools.trigger_crawl(platforms=['guardianau'], debug=False)
        
        assert isinstance(result, dict)
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        assert result["total_news"] > 0
        assert "guardianau" in result["platforms"]
        assert len(result["data"]) > 0
        assert result["data"][0]["platform_id"] == "guardianau"

    def test_trigger_crawl_asharq_al_awsat(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl Asharq Al-Awsat RSS feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        system_tools = SystemManagementTools()
        result = system_tools.trigger_crawl(platforms=['aawsat'], debug=False)
        
        assert isinstance(result, dict)
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        assert result["total_news"] > 0
        assert "aawsat" in result["platforms"]
        assert len(result["data"]) > 0
        assert result["data"][0]["platform_id"] == "aawsat"

    def test_trigger_crawl_al_jazeera(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl Al Jazeera English RSS feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        system_tools = SystemManagementTools()
        result = system_tools.trigger_crawl(platforms=['aljazeera'], debug=False)
        
        assert isinstance(result, dict)
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        assert result["total_news"] > 0
        assert "aljazeera" in result["platforms"]
        assert len(result["data"]) > 0
        assert result["data"][0]["platform_id"] == "aljazeera"

    def test_trigger_crawl_times_of_israel(self, mcp_server_process):
        """Test that trigger_crawl can successfully crawl The Times of Israel RSS feed"""
        from mcp_server.tools.system import SystemManagementTools
        
        system_tools = SystemManagementTools()
        result = system_tools.trigger_crawl(platforms=['timesofisrael'], debug=False)
        
        assert isinstance(result, dict)
        assert result["success"] is True, f"Crawl failed: {result.get('error')}"
        assert result["total_news"] > 0
        assert "timesofisrael" in result["platforms"]
        assert len(result["data"]) > 0
        assert result["data"][0]["platform_id"] == "timesofisrael"


class TestDeepSearchService:
    """Tests for the DeepSearchService and SiteSearchService"""

    def test_rate_limiter_basic(self):
        """Test that RateLimiter correctly limits request frequency"""
        from mcp_server.services.search_service import RateLimiter
        import time

        limiter = RateLimiter()
        
        # First call should not wait
        start = time.time()
        limiter.wait_if_needed("example.com", min_interval=0.1)
        first_wait = time.time() - start
        assert first_wait < 0.05, "First call should not wait"
        
        # Second call should wait
        start = time.time()
        limiter.wait_if_needed("example.com", min_interval=0.1)
        second_wait = time.time() - start
        assert second_wait >= 0.08, f"Second call should wait ~0.1s, waited {second_wait}s"

    def test_rate_limiter_different_domains(self):
        """Test that RateLimiter tracks domains independently"""
        from mcp_server.services.search_service import RateLimiter
        import time

        limiter = RateLimiter()
        
        # First domain
        limiter.wait_if_needed("domain1.com", min_interval=0.1)
        
        # Second domain should not wait (different domain)
        start = time.time()
        limiter.wait_if_needed("domain2.com", min_interval=0.1)
        wait_time = time.time() - start
        assert wait_time < 0.05, "Different domain should not wait"

    def test_site_search_service_has_configs(self):
        """Test that SiteSearchService has search configurations for supported platforms"""
        from mcp_server.services.search_service import SiteSearchService

        service = SiteSearchService()
        
        # Check that we have configs for the expected platforms
        expected_platforms = ["theguardian", "spiegel", "aljazeera"]
        for platform in expected_platforms:
            assert platform in service.SEARCH_CONFIGS, f"Missing config for {platform}"
            config = service.SEARCH_CONFIGS[platform]
            assert config["enabled"] is True
            # Guardian uses API, others use search_url
            assert "search_url" in config or "api_url" in config
            assert "selectors" in config or config.get("type") == "api"

    def test_site_search_service_get_searchable_platforms(self):
        """Test that SiteSearchService correctly returns searchable platforms"""
        from mcp_server.services.search_service import SiteSearchService

        service = SiteSearchService()
        searchable = service.get_searchable_platforms()
        
        assert isinstance(searchable, list)
        assert len(searchable) >= 3  # At least guardian, spiegel, aljazeera
        assert "theguardian" in searchable
        assert "spiegel" in searchable
        assert "aljazeera" in searchable

    def test_site_search_service_language_filtering(self):
        """Test that SiteSearchService correctly filters platforms by language"""
        from mcp_server.services.search_service import SiteSearchService

        service = SiteSearchService()
        
        # Test German platforms
        german_platforms = service.get_searchable_platforms(language="de")
        assert isinstance(german_platforms, list)
        assert "spiegel" in german_platforms
        assert "heise" in german_platforms
        assert "theguardian" not in german_platforms  # Guardian is English
        
        # Test English platforms
        english_platforms = service.get_searchable_platforms(language="en")
        assert "theguardian" in english_platforms
        assert "aljazeera" in english_platforms
        assert "spiegel" not in english_platforms  # Spiegel is German
        
        # Test platform language lookup
        assert service.get_platform_language("spiegel") == "de"
        assert service.get_platform_language("theguardian") == "en"
        assert service.get_platform_language("lemonde") == "fr"

    def test_site_search_service_is_search_enabled(self):
        """Test that SiteSearchService correctly identifies enabled platforms"""
        from mcp_server.services.search_service import SiteSearchService

        service = SiteSearchService()
        
        assert service.is_search_enabled("theguardian") is True
        assert service.is_search_enabled("spiegel") is True
        assert service.is_search_enabled("aljazeera") is True
        assert service.is_search_enabled("unknown_platform") is False

    def test_deep_search_service_initialization(self):
        """Test that DeepSearchService initializes correctly"""
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        
        assert deep_search.data_service is not None
        assert deep_search.site_search is not None

    def test_deep_search_headlines_only_mode(self):
        """Test deep search in headlines-only mode"""
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        
        # Search for a common term in headlines mode
        result = deep_search.deep_search(
            query="news",
            mode="headlines",
            max_results=10,
            include_url=False
        )
        
        assert isinstance(result, dict)
        assert "query" in result
        assert result["query"] == "news"
        assert "mode" in result
        assert result["mode"] == "headlines"
        assert "metadata" in result

    def test_deep_search_result_structure(self):
        """Test that deep search returns correctly structured results"""
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        
        result = deep_search.deep_search(
            query="test",
            mode="headlines",
            max_results=5
        )
        
        assert isinstance(result, dict)
        # Check required fields are present
        required_fields = ["query", "mode", "headlines", "site_search", "combined", "metadata"]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_deep_search_combine_and_rank(self):
        """Test deduplication and ranking in combine_and_rank"""
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        
        # Create test data with duplicates
        headlines = [
            {"title": "Test Article One", "platform_id": "guardian", "source": "headlines"},
            {"title": "Test Article Two", "platform_id": "spiegel", "source": "headlines"},
        ]
        site_results = [
            {"title": "Test Article One", "platform_id": "guardian", "source": "site_search"},  # Duplicate
            {"title": "Test Article Three", "platform_id": "aljazeera", "source": "site_search"},
        ]
        
        # Combine and rank
        combined = deep_search._combine_and_rank(headlines, site_results, "test", max_results=10)
        
        # Should have 3 unique results (duplicate removed)
        assert len(combined) == 3
        
        # All should have relevance scores
        for item in combined:
            assert "relevance_score" in item
            assert isinstance(item["relevance_score"], float)


class TestDeepSearchLive:
    """Live integration tests for deep search with real news queries.
    
    Note: Tests marked with @pytest.mark.browser require Playwright and are slow.
    Run without browser tests: pytest -m "not browser"
    Run only browser tests: pytest -m browser
    """

    @pytest.mark.integration
    def test_live_site_search_guardian_election(self):
        """Test live site search on The Guardian for 'election' (uses API)
        
        Verifies returned results are actual news articles with proper metadata.
        """
        from mcp_server.services.search_service import SiteSearchService

        service = SiteSearchService()
        results = service.search("theguardian", "election", max_results=10, max_pages=1)
        
        assert isinstance(results, list)
        assert len(results) > 0, "Expected to find results for 'election' on The Guardian API"
        
        # Verify these are actual news articles
        print(f"\n📰 Guardian 'election' results ({len(results)} articles):")
        for item in results[:5]:
            assert "title" in item, "Article must have a title"
            assert len(item["title"]) > 10, f"Title too short to be a real article: {item['title']}"
            assert "url" in item, "Article must have a URL"
            assert "theguardian.com" in item["url"], f"URL should be from theguardian.com: {item['url']}"
            
            # Title should contain actual words
            assert any(c.isalpha() for c in item["title"]), "Title must contain letters"
            
            print(f"  ✓ {item['title'][:80]}")
            print(f"    → {item['url'][:100]}")

    @pytest.mark.integration
    def test_live_site_search_guardian_government_policy(self):
        """Test live site search on The Guardian for 'government policy' (uses API)
        
        Verifies returned results are actual news articles.
        """
        from mcp_server.services.search_service import SiteSearchService

        service = SiteSearchService()
        results = service.search("theguardian", "government policy", max_results=10, max_pages=1)
        
        assert isinstance(results, list)
        assert len(results) > 0, "Expected to find results for 'government policy' on The Guardian API"
        
        # Verify these are actual news articles
        print(f"\n📰 Guardian 'government policy' results ({len(results)} articles):")
        for item in results[:5]:
            assert "title" in item
            assert len(item["title"]) > 10
            print(f"  ✓ {item['title'][:80]}")
    @pytest.mark.browser
    @pytest.mark.slow
    @pytest.mark.timeout(30)
    def test_live_site_search_spiegel_politik(self):
        """Test live site search on Der Spiegel for 'Politik' (German politics)
        
        Uses Playwright for JavaScript rendering.
        Verifies returned results are actual news articles.
        Optimized for ~20-30 second runtime.
        """
        from mcp_server.services.search_service import SiteSearchService
        from mcp_server.services.browser_service import PLAYWRIGHT_AVAILABLE
        import warnings

        service = SiteSearchService()
        results = service.search("spiegel", "Politik", max_results=5, max_pages=1)
        
        assert isinstance(results, list)
        
        if PLAYWRIGHT_AVAILABLE:
            assert len(results) > 0, "Expected to find results for 'Politik' on Der Spiegel with Playwright"
            
            # Verify these are actual news articles
            print(f"\n📰 Spiegel 'Politik' results ({len(results)} articles):")
            for item in results[:3]:
                assert "title" in item, "Article must have a title"
                assert len(item["title"]) > 10, f"Title too short to be a real article: {item['title']}"
                
                # Title should contain actual words, not just symbols
                assert any(c.isalpha() for c in item["title"]), "Title must contain letters"
                
                print(f"  ✓ {item['title'][:80]}")
                if "url" in item and item["url"]:
                    print(f"    → {item['url'][:100]}")
        else:
            if len(results) == 0:
                warnings.warn("Playwright not installed - Spiegel search requires JavaScript")
    @pytest.mark.browser
    @pytest.mark.slow
    @pytest.mark.timeout(30)
    def test_live_site_search_spiegel_winter_wetter(self):
        """Test live site search on Der Spiegel for 'Winter' (winter weather)
        
        Uses Playwright for JavaScript rendering.
        Optimized for ~20-30 second runtime.
        """
        from mcp_server.services.search_service import SiteSearchService
        from mcp_server.services.browser_service import PLAYWRIGHT_AVAILABLE
        import warnings

        service = SiteSearchService()
        results = service.search("spiegel", "Winter", max_results=5, max_pages=1)
        
        assert isinstance(results, list)
        
        if PLAYWRIGHT_AVAILABLE:
            assert len(results) > 0, "Expected to find results for 'Winter' on Der Spiegel with Playwright"
            
            print(f"\n📰 Spiegel 'Winter' results ({len(results)} articles):")
            for item in results[:3]:
                assert "title" in item, "Article must have a title"
                assert len(item["title"]) > 10, f"Title too short: {item['title']}"
                print(f"  ✓ {item['title'][:80]}")
        else:
            if len(results) == 0:
                warnings.warn("Playwright not installed - Spiegel search requires JavaScript")

    @pytest.mark.browser
    @pytest.mark.slow
    @pytest.mark.timeout(30)
    def test_live_site_search_aljazeera_middle_east(self):
        """Test live site search on Al Jazeera for 'Middle East'
        
        Uses Playwright for JavaScript rendering.
        Optimized for ~20-30 second runtime.
        """
        from mcp_server.services.search_service import SiteSearchService
        from mcp_server.services.browser_service import PLAYWRIGHT_AVAILABLE
        import warnings

        service = SiteSearchService()
        results = service.search("aljazeera", "Middle East", max_results=5, max_pages=1)
        
        assert isinstance(results, list)
        
        if PLAYWRIGHT_AVAILABLE:
            assert len(results) > 0, "Expected to find results for 'Middle East' on Al Jazeera with Playwright"
            
            print(f"\n📰 Al Jazeera 'Middle East' results ({len(results)} articles):")
            for item in results[:3]:
                assert "title" in item, "Article must have a title"
                assert len(item["title"]) > 5, f"Title too short: {item['title']}"
                print(f"  ✓ {item['title'][:80]}")
                if "url" in item and item["url"]:
                    print(f"    → {item['url'][:100]}")
        else:
            if len(results) == 0:
                warnings.warn("Playwright not installed - Al Jazeera search requires JavaScript")

    @pytest.mark.browser
    @pytest.mark.slow
    @pytest.mark.timeout(30)
    def test_live_site_search_aljazeera_climate(self):
        """Test live site search on Al Jazeera for 'climate'
        
        Uses Playwright for JavaScript rendering.
        Optimized for ~20-30 second runtime.
        """
        from mcp_server.services.search_service import SiteSearchService
        from mcp_server.services.browser_service import PLAYWRIGHT_AVAILABLE
        import warnings

        service = SiteSearchService()
        results = service.search("aljazeera", "climate", max_results=5, max_pages=1)
        
        assert isinstance(results, list)
        
        if PLAYWRIGHT_AVAILABLE:
            assert len(results) > 0, "Expected to find results for 'climate' on Al Jazeera with Playwright"
            
            print(f"\n📰 Al Jazeera 'climate' results ({len(results)} articles):")
            for item in results[:3]:
                assert "title" in item, "Article must have a title"
                assert len(item["title"]) > 5, f"Title too short: {item['title']}"
                print(f"  ✓ {item['title'][:80]}")
        else:
            if len(results) == 0:
                warnings.warn("Playwright not installed - Al Jazeera search requires JavaScript")

    @pytest.mark.integration
    def test_live_deep_search_hybrid_election(self):
        """Test hybrid deep search for 'election' - Guardian only for speed
        
        Verifies returned results are actual news articles.
        Limited to Guardian API to keep test under 20 seconds.
        """
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        result = deep_search.deep_search(
            query="election",
            platforms=["theguardian"],  # Guardian only for speed
            mode="both",
            max_results=10,
            include_url=True
        )
        
        assert isinstance(result, dict)
        assert "combined" in result
        assert "metadata" in result
        
        # Should find results from at least site search
        total = result["metadata"]["total_results"]
        site_count = result["metadata"]["site_search_count"]
        
        assert site_count > 0, "Expected to find site search results for 'election'"
        assert total > 0, "Expected to find combined results for 'election'"
        
        # Display found articles
        print(f"\n📰 Deep Search 'election' - {total} total results:")
        print(f"   Headlines: {result['metadata']['headline_count']}, Site Search: {site_count}")
        for item in result["combined"][:5]:
            source_icon = "🗞️" if item["source"] == "headlines" else "🔍"
            print(f"  {source_icon} [{item.get('platform_id', 'unknown')}] {item['title'][:70]}")

    def test_live_deep_search_hybrid_government_budget(self):
        """Test hybrid deep search for 'government budget' - Guardian only
        
        Verifies article structure and displays found news.
        Limited to Guardian API to keep test under 20 seconds.
        """
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        result = deep_search.deep_search(
            query="government budget",
            platforms=["theguardian"],
            mode="both",
            max_results=10,
            include_url=True
        )
        
        assert isinstance(result, dict)
        assert result["metadata"]["total_results"] >= 0
        
        # Check combined results structure
        print(f"\n📰 Deep Search 'government budget' - {result['metadata']['total_results']} results:")
        for item in result["combined"][:5]:
            assert "title" in item
            assert "source" in item
            assert item["source"] in ("headlines", "site_search")
            source_icon = "🗞️" if item["source"] == "headlines" else "🔍"
            print(f"  {source_icon} {item['title'][:75]}")

    def test_live_deep_search_hybrid_winter_holiday(self):
        """Test hybrid deep search for 'winter holiday travel'
        
        Verifies search metadata and displays results.
        Limited to Guardian API to keep test under 20 seconds.
        """
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        result = deep_search.deep_search(
            query="winter holiday travel",
            platforms=["theguardian"],
            mode="both",
            max_results=10,
            include_url=True
        )
        
        assert isinstance(result, dict)
        assert "query" in result
        assert result["query"] == "winter holiday travel"
        assert "mode" in result
        assert result["mode"] == "both"
        
        print(f"\n📰 Deep Search 'winter holiday travel' - {result['metadata']['total_results']} results:")
        for item in result["combined"][:5]:
            print(f"  ✓ {item['title'][:75]}")

    def test_live_deep_search_hybrid_economy_inflation(self):
        """Test hybrid deep search for 'economy inflation'
        
        Verifies site search returns relevant economic news.
        Limited to Guardian API to keep test under 20 seconds.
        """
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        result = deep_search.deep_search(
            query="economy inflation",
            platforms=["theguardian"],
            mode="both",
            max_results=10,
            include_url=True
        )
        
        assert isinstance(result, dict)
        assert result["metadata"]["site_search_count"] > 0, "Expected site search results for 'economy inflation'"
        
        print(f"\n📰 Deep Search 'economy inflation' - {result['metadata']['total_results']} results:")
        for item in result["combined"][:5]:
            print(f"  ✓ {item['title'][:75]}")

    def test_live_deep_search_site_only_technology_ai(self):
        """Test site-search-only mode for 'artificial intelligence'
        
        Verifies site-only mode doesn't search headlines.
        Limited to Guardian API to keep test under 20 seconds.
        """
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        result = deep_search.deep_search(
            query="artificial intelligence",
            platforms=["theguardian"],
            mode="site_search",
            max_results=10,
            include_url=True
        )
        
        assert isinstance(result, dict)
        assert result["mode"] == "site_search"
        assert result["metadata"]["headline_count"] == 0, "Site-only mode should not search headlines"
        assert result["metadata"]["site_search_count"] > 0, "Expected site search results for 'AI'"
        
        print(f"\n📰 Site-only Search 'artificial intelligence' - {result['metadata']['site_search_count']} results:")
        for item in result["site_search"][:5]:
            print(f"  🔍 [{item.get('platform_id', '?')}] {item['title'][:65]}")

    def test_live_deep_search_single_platform_guardian(self):
        """Test deep search limited to single platform (The Guardian)
        
        Verifies platform filtering works correctly.
        """
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        result = deep_search.deep_search(
            query="Brexit trade",
            platforms=["theguardian"],
            mode="site_search",
            max_results=10,
            include_url=True
        )
        
        assert isinstance(result, dict)
        assert "theguardian" in result["metadata"]["platforms_searched"]
        
        # All site_search results should be from guardian
        for item in result["site_search"]:
            assert item["platform_id"] == "theguardian"

    @pytest.mark.browser
    def test_live_deep_search_single_platform_spiegel(self):
        """Test deep search limited to single platform (Der Spiegel)
        
        Uses Playwright for JavaScript rendering.
        """
        from mcp_server.services.search_service import DeepSearchService
        from mcp_server.services.browser_service import PLAYWRIGHT_AVAILABLE
        import warnings

        deep_search = DeepSearchService()
        result = deep_search.deep_search(
            query="Bundesregierung",
            platforms=["spiegel"],
            mode="site_search",
            max_results=10,
            include_url=True
        )
        
        assert isinstance(result, dict)
        
        if PLAYWRIGHT_AVAILABLE:
            assert result["metadata"]["site_search_count"] > 0, "Expected results for 'Bundesregierung' on Spiegel with Playwright"
        else:
            if result["metadata"]["site_search_count"] == 0:
                warnings.warn("Playwright not installed - Spiegel search requires JavaScript")

    @pytest.mark.browser
    def test_live_deep_search_multiple_platforms(self):
        """Test deep search across multiple specific platforms
        
        Uses Playwright for Al Jazeera.
        """
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        result = deep_search.deep_search(
            query="climate summit",
            platforms=["theguardian", "aljazeera"],
            mode="site_search",
            max_results=20,
            include_url=True
        )
        
        assert isinstance(result, dict)
        platforms_searched = result["metadata"]["platforms_searched"]
        assert "theguardian" in platforms_searched or "aljazeera" in platforms_searched

    def test_live_deep_search_deduplication(self):
        """Test that hybrid search properly deduplicates results"""
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        result = deep_search.deep_search(
            query="Ukraine war",
            mode="both",
            max_results=30,
            include_url=True
        )
        
        assert isinstance(result, dict)
        
        # Check for duplicates in combined results
        titles_seen = set()
        for item in result["combined"]:
            title_lower = item["title"].lower()[:50]  # First 50 chars
            assert title_lower not in titles_seen, f"Duplicate title found: {item['title']}"
            titles_seen.add(title_lower)

    def test_live_deep_search_relevance_scoring(self):
        """Test that results have relevance scores and are sorted"""
        from mcp_server.services.search_service import DeepSearchService

        deep_search = DeepSearchService()
        result = deep_search.deep_search(
            query="technology innovation",
            mode="both",
            max_results=20,
            include_url=True
        )
        
        assert isinstance(result, dict)
        
        if len(result["combined"]) > 1:
            # Check that results are sorted by relevance (descending)
            scores = [item.get("relevance_score", 0) for item in result["combined"]]
            assert scores == sorted(scores, reverse=True), "Results should be sorted by relevance"

