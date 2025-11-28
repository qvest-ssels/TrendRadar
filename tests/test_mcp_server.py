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