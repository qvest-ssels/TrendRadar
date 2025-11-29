.PHONY: test test-verbose clean help start-server stop-server server-status start-rest-api stop-rest-api start-news-chat stop-news-chat news-chat-status start-all stop-all status

# Default target
help:
	@echo "Available targets:"
	@echo ""
	@echo "  === Testing ==="
	@echo "  test           - Run all tests"
	@echo "  test-verbose   - Run tests with verbose output"
	@echo "  test-mcp       - Test MCP server functionality"
	@echo "  test-news-chat - Test News Chat service"
	@echo "  test-platforms - Test all configured platforms"
	@echo "  test-crawl     - Test crawling for specific platform (usage: make test-crawl PLATFORM=spiegel)"
	@echo "  quick-test     - Run quick crawl test for all platforms"
	@echo ""
	@echo "  === MCP Server (port 3333) ==="
	@echo "  start-server   - Start MCP server in background"
	@echo "  stop-server    - Stop running MCP server"
	@echo "  server-status  - Check MCP server status"
	@echo ""
	@echo "  === REST API (port 3334) ==="
	@echo "  start-rest-api - Start REST API wrapper for News Chat"
	@echo "  stop-rest-api  - Stop REST API wrapper"
	@echo ""
	@echo "  === News Chat (port 8000) ==="
	@echo "  start-news-chat - Start News Chat web service"
	@echo "  stop-news-chat  - Stop News Chat web service"
	@echo "  news-chat-status - Check News Chat status"
	@echo ""
	@echo "  === Convenience ==="
	@echo "  start-all      - Start all services (REST API + News Chat)"
	@echo "  stop-all       - Stop all services"
	@echo "  status         - Show status of all services"
	@echo "  clean          - Clean up cache files"
	@echo "  help           - Show this help message"

# Run tests
test:
	./.venv/bin/python -m pytest tests/ -q

# Run tests with verbose output
test-verbose:
	./.venv/bin/python -m pytest tests/ -v

# Test Spiegel RSS feed
test-spiegel:
	./.venv/bin/python test_spiegel.py

# Test all configured platforms
test-platforms:
	./.venv/bin/python test_all_platforms.py

# Test MCP server functionality
test-mcp:
	./.venv/bin/python -m pytest tests/test_mcp_server.py -v

# Start MCP server in background
start-server:
	@echo "Starting MCP server..."
	@if [ -f .mcp_server.pid ] && kill -0 `cat .mcp_server.pid` 2>/dev/null; then \
		echo "MCP server is already running (PID: `cat .mcp_server.pid`)"; \
		exit 1; \
	fi
	@uv run python -m mcp_server.server --transport http --host 127.0.0.1 --port 3333 > .mcp_server.log 2>&1 & \
	echo $$! > .mcp_server.pid
	@echo "MCP server started (PID: `cat .mcp_server.pid`)"
	@echo "Server URL: http://localhost:3333/mcp"
	@echo "Logs: .mcp_server.log"

# Stop running MCP server
stop-server:
	@echo "Stopping MCP server..."
	@if [ ! -f .mcp_server.pid ]; then \
		echo "No MCP server PID file found"; \
		exit 1; \
	fi
	@PID=`cat .mcp_server.pid`; \
	if kill -0 $$PID 2>/dev/null; then \
		kill $$PID; \
		echo "Sent SIGTERM to MCP server (PID: $$PID)"; \
		for i in 1 2 3 4 5; do \
			if kill -0 $$PID 2>/dev/null; then \
				sleep 1; \
			else \
				break; \
			fi; \
		done; \
		if kill -0 $$PID 2>/dev/null; then \
			kill -9 $$PID 2>/dev/null; \
			echo "Force killed MCP server (PID: $$PID)"; \
		fi; \
	else \
		echo "MCP server process (PID: $$PID) not found"; \
	fi
	@rm -f .mcp_server.pid
	@echo "MCP server stopped"

# Check MCP server status
server-status:
	@if [ -f .mcp_server.pid ] && kill -0 `cat .mcp_server.pid` 2>/dev/null; then \
		echo "MCP server is running (PID: `cat .mcp_server.pid`)"; \
		echo "Server URL: http://localhost:3333/mcp"; \
		if [ -f .mcp_server.log ]; then \
			echo "Last log entries:"; \
			tail -5 .mcp_server.log; \
		fi; \
	else \
		echo "MCP server is not running"; \
		if [ -f .mcp_server.pid ]; then \
			echo "Removing stale PID file"; \
			rm -f .mcp_server.pid; \
		fi; \
	fi

# Run quick test - crawl all platforms once
quick-test:
	./.venv/bin/python main.py --quick-test

# Test crawling for specific platform (usage: make test-crawl PLATFORM=spiegel)
test-crawl:
	@if [ -z "$(PLATFORM)" ]; then \
		echo "Usage: make test-crawl PLATFORM=<platform_id>"; \
		echo "Example: make test-crawl PLATFORM=spiegel"; \
		echo "Or test all platforms: make test-crawl PLATFORM=all"; \
		exit 1; \
	fi
	./.venv/bin/python main.py --test-crawl $(PLATFORM)

# Clean up cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

# Start REST API wrapper for News Chat (port 3334, MCP is on 3333)
start-rest-api:
	@echo "Starting REST API wrapper..."
	@if [ -f .rest_api.pid ] && kill -0 `cat .rest_api.pid` 2>/dev/null; then \
		echo "REST API is already running (PID: `cat .rest_api.pid`)"; \
		exit 1; \
	fi
	@uv run python -m uvicorn mcp_server.http_api:app --host 127.0.0.1 --port 3334 > .rest_api.log 2>&1 & \
	echo $$! > .rest_api.pid
	@sleep 2
	@echo "REST API started (PID: `cat .rest_api.pid`)"
	@echo "Health check: http://localhost:3334/health"
	@echo "Tools list: http://localhost:3334/tools"
	@echo "Logs: .rest_api.log"

# Stop REST API wrapper
stop-rest-api:
	@echo "Stopping REST API..."
	@if [ -f .rest_api.pid ]; then \
		PID=`cat .rest_api.pid`; \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			echo "REST API stopped (PID: $$PID)"; \
		else \
			echo "REST API process not found"; \
		fi; \
		rm -f .rest_api.pid; \
	else \
		echo "No REST API PID file found"; \
	fi

# Start News Chat web service (port 8000)
start-news-chat:
	@echo "Starting News Chat..."
	@if [ -f news-chat/.news_chat.pid ] && kill -0 `cat news-chat/.news_chat.pid` 2>/dev/null; then \
		echo "News Chat is already running (PID: `cat news-chat/.news_chat.pid`)"; \
		exit 1; \
	fi
	@cd news-chat && VIRTUAL_ENV="$$(pwd)/.venv" uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 > .news_chat.log 2>&1 & \
	echo $$! > .news_chat.pid
	@sleep 2
	@echo "News Chat started (PID: `cat news-chat/.news_chat.pid`)"
	@echo "Web UI: http://localhost:8000"
	@echo "API Status: http://localhost:8000/api/status"
	@echo "Logs: news-chat/.news_chat.log"

# Stop News Chat web service
stop-news-chat:
	@echo "Stopping News Chat..."
	@if [ -f news-chat/.news_chat.pid ]; then \
		PID=`cat news-chat/.news_chat.pid`; \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			echo "News Chat stopped (PID: $$PID)"; \
		else \
			echo "News Chat process not found"; \
		fi; \
		rm -f news-chat/.news_chat.pid; \
	else \
		echo "No News Chat PID file found"; \
	fi

# Check News Chat status
news-chat-status:
	@if [ -f news-chat/.news_chat.pid ] && kill -0 `cat news-chat/.news_chat.pid` 2>/dev/null; then \
		echo "News Chat is running (PID: `cat news-chat/.news_chat.pid`)"; \
		echo "Web UI: http://localhost:8000"; \
		curl -s http://localhost:8000/api/status 2>/dev/null || echo "API not responding"; \
	else \
		echo "News Chat is not running"; \
		if [ -f news-chat/.news_chat.pid ]; then \
			rm -f news-chat/.news_chat.pid; \
		fi; \
	fi

# Start all services (REST API + News Chat)
start-all: start-rest-api start-news-chat
	@echo ""
	@echo "All services started!"
	@echo "  REST API: http://localhost:3334"
	@echo "  News Chat: http://localhost:8000"

# Stop all services
stop-all: stop-news-chat stop-rest-api
	@echo "All services stopped"

# Show status of all services
status: server-status
	@echo ""
	@echo "=== REST API (port 3334) ==="
	@if [ -f .rest_api.pid ] && kill -0 `cat .rest_api.pid` 2>/dev/null; then \
		echo "REST API is running (PID: `cat .rest_api.pid`)"; \
		curl -s http://localhost:3334/health 2>/dev/null || echo "API not responding"; \
	else \
		echo "REST API is not running"; \
	fi
	@echo ""
	@echo "=== News Chat (port 8000) ==="
	@$(MAKE) -s news-chat-status

# Test News Chat service
test-news-chat:
	@echo "Testing News Chat..."
	cd news-chat && PYTHONPATH="$$(pwd)" .venv/bin/python -m pytest tests/ -v

# Clean up cache and temp files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.pyd" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true
	rm -f .mcp_server.pid .mcp_server.log .rest_api.pid .rest_api.log
	rm -f news-chat/.news_chat.pid news-chat/.news_chat.log news-chat/server.log