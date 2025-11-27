.PHONY: test test-verbose clean help start-server stop-server server-status

# Default target
help:
	@echo "Available targets:"
	@echo "  test           - Run all tests"
	@echo "  test-verbose   - Run tests with verbose output"
	@echo "  test-spiegel   - Test Spiegel RSS feed integration"
	@echo "  test-platforms - Test all configured platforms"
	@echo "  test-mcp       - Test MCP server functionality"
	@echo "  start-server   - Start MCP server in background"
	@echo "  stop-server    - Stop running MCP server"
	@echo "  server-status  - Check MCP server status"
	@echo "  quick-test     - Run quick crawl test for all platforms"
	@echo "  test-crawl     - Test crawling for specific platform (usage: make test-crawl PLATFORM=spiegel)"
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
	find . -type d -name ".coverage" -exec rm -rf {} +
	rm -f .mcp_server.pid .mcp_server.log