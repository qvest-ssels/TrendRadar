"""
Tests for News Chat API endpoints
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health and status endpoints."""
    
    def test_root_returns_html(self, client):
        """Test that root returns the chat UI."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "ok"]
    
    def test_status_endpoint(self, client):
        """Test status endpoint returns connection info."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "ollama" in data
        assert "mcp" in data
        assert "connected" in data["ollama"]
        assert "connected" in data["mcp"]


class TestChatEndpoint:
    """Test chat API endpoint."""
    
    def test_chat_requires_messages(self, client):
        """Test that chat endpoint requires messages."""
        response = client.post("/api/chat", json={})
        assert response.status_code == 422  # Validation error
    
    def test_chat_accepts_valid_request(self, client):
        """Test chat with valid request structure."""
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False
            }
        )
        # May fail if Ollama not running, but should not be 422
        assert response.status_code in [200, 500]
    
    def test_chat_streaming_headers(self, client):
        """Test that streaming chat returns SSE headers."""
        with client.stream(
            "POST",
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": True
            }
        ) as response:
            # Check headers even if Ollama not running
            if response.status_code == 200:
                assert "text/event-stream" in response.headers.get("content-type", "")


class TestMessageValidation:
    """Test message format validation."""
    
    def test_message_requires_role(self, client):
        """Test that messages require role field."""
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"content": "Hello"}],
                "stream": False
            }
        )
        assert response.status_code == 422
    
    def test_message_requires_content(self, client):
        """Test that messages require content field."""
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user"}],
                "stream": False
            }
        )
        assert response.status_code == 422
    
    def test_valid_message_format(self, client):
        """Test valid message format is accepted."""
        response = client.post(
            "/api/chat",
            json={
                "messages": [
                    {"role": "user", "content": "What's the weather?"}
                ],
                "stream": False
            }
        )
        # Should not be validation error
        assert response.status_code != 422
