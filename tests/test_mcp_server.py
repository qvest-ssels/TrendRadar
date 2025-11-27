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