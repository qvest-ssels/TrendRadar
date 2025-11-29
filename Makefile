.PHONY: test test-verbose clean help start-server stop-server server-status start-rest-api stop-rest-api start-ollama stop-ollama ollama-status start-news-chat stop-news-chat news-chat-status start-woodchuck-server stop-woodchuck-server woodchuck-status generate-woodchuck start-all start-all-warmup stop-all status check-cache warmup warmup-force warmup-list

# Variables
UV := uv
PYTHON := python

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
	@echo "  === Ollama (port 11434) ==="
	@echo "  start-ollama   - Start Ollama LLM service"
	@echo "  stop-ollama    - Stop Ollama service"
	@echo "  ollama-status  - Check Ollama status and models"
	@echo ""
	@echo "  === News Chat (port 8000) ==="
	@echo "  start-news-chat - Start News Chat web service"
	@echo "  stop-news-chat  - Stop News Chat web service"
	@echo "  news-chat-status - Check News Chat status"
	@echo ""
	@echo "  === Woodchuck News (port 8080) ==="
	@echo "  start-woodchuck-server   - Start static site server"
	@echo "  stop-woodchuck-server    - Stop static site server"
	@echo "  woodchuck-status         - Check Woodchuck News status"
	@echo "  generate-woodchuck       - Regenerate static site"
	@echo ""
	@echo "  === Warmup & Cache ==="
	@echo "  check-cache    - Check if cached output exists for today"
	@echo "  warmup         - Run warmup crawl (only if no cache)"
	@echo "  warmup-force   - Force warmup crawl (even with cache)"
	@echo "  warmup-list    - List platforms for warmup"
	@echo ""
	@echo "  === Convenience ==="
	@echo "  start-all        - Start all services (REST API + News Chat)"
	@echo "  start-all-warmup - Start all services with warmup"
	@echo "  stop-all         - Stop all services"
	@echo "  status           - Show status of all services"
	@echo "  clean            - Clean up cache files"
	@echo "  help             - Show this help message"

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
			kill $$PID 2>/dev/null || true; \
			echo "REST API stopped (PID: $$PID)"; \
		fi; \
		rm -f .rest_api.pid; \
	fi
	@# Also kill any orphan processes by pattern
	@pkill -f "uvicorn mcp_server.http_api:app.*3334" 2>/dev/null || true
	@sleep 0.5
	@if curl -s http://localhost:3334/health > /dev/null 2>&1; then \
		echo "Warning: REST API still running, force killing..."; \
		pkill -9 -f "uvicorn mcp_server.http_api:app" 2>/dev/null || true; \
	else \
		echo "REST API stopped"; \
	fi

# Start Ollama LLM service (port 11434)
start-ollama:
	@echo "Starting Ollama..."
	@if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then \
		echo "Ollama is already running"; \
		curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | head -5 || true; \
	else \
		ollama serve > .ollama.log 2>&1 & \
		echo $$! > .ollama.pid; \
		sleep 3; \
		if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then \
			echo "Ollama started"; \
			echo "Available models:"; \
			curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | sed 's/"name":"//g' | sed 's/"//g' || echo "  (none - run: ollama pull qwen2.5:7b)"; \
		else \
			echo "Failed to start Ollama. Is it installed? (brew install ollama)"; \
		fi; \
	fi

# Stop Ollama service
stop-ollama:
	@echo "Stopping Ollama..."
	@if [ -f .ollama.pid ]; then \
		PID=`cat .ollama.pid`; \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			echo "Ollama stopped (PID: $$PID)"; \
		else \
			echo "Ollama process not found"; \
		fi; \
		rm -f .ollama.pid; \
	else \
		pkill -f "ollama serve" 2>/dev/null && echo "Ollama stopped" || echo "Ollama not running"; \
	fi

# Check Ollama status
ollama-status:
	@if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then \
		echo "Ollama is running on http://localhost:11434"; \
		echo "Available models:"; \
		curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | sed 's/"name":"//g' | sed 's/"//g' || echo "  (none)"; \
	else \
		echo "Ollama is not running"; \
	fi

# Start News Chat web service (port 8000)
start-news-chat:
	@echo "Starting News Chat..."
	@if [ -f news-chat/.news_chat.pid ] && kill -0 `cat news-chat/.news_chat.pid` 2>/dev/null; then \
		echo "News Chat is already running (PID: `cat news-chat/.news_chat.pid`)"; \
		exit 1; \
	fi
	@(cd news-chat && VIRTUAL_ENV="$$(pwd)/.venv" $(UV) run uvicorn app.main:app --host 127.0.0.1 --port 8000 > .news_chat.log 2>&1) & echo $$! > news-chat/.news_chat.pid
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
			kill $$PID 2>/dev/null || true; \
			echo "News Chat stopped (PID: $$PID)"; \
		fi; \
		rm -f news-chat/.news_chat.pid; \
	fi
	@# Also kill any orphan uvicorn processes on port 8000
	@pkill -f "uvicorn app.main:app.*8000" 2>/dev/null || true
	@sleep 0.5
	@if curl -s http://localhost:8000/api/status > /dev/null 2>&1; then \
		echo "Warning: News Chat still running, force killing..."; \
		pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true; \
		lsof -ti:8000 | xargs kill -9 2>/dev/null || true; \
	else \
		echo "News Chat stopped"; \
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

# ==================== Woodchuck News Static Site ====================

# Generate Woodchuck News static site from output data
generate-woodchuck:
	@echo "Generating Woodchuck News static site..."
	cd woodchuck-news && $(UV) run python -m generator.generator
	@echo "Static site generated in woodchuck-news/output/"

# Start Woodchuck News development server (port 8080)
start-woodchuck-server:
	@echo "Starting Woodchuck News server on http://localhost:8080..."
	@if [ -f woodchuck-news/.woodchuck.pid ] && kill -0 `cat woodchuck-news/.woodchuck.pid` 2>/dev/null; then \
		echo "Woodchuck News server is already running (PID: `cat woodchuck-news/.woodchuck.pid`)"; \
	else \
		$(UV) run python -m http.server 8080 --directory woodchuck-news/output > /dev/null 2>&1 & echo $$! > woodchuck-news/.woodchuck.pid; \
		sleep 1; \
		echo "Woodchuck News server started (PID: `cat woodchuck-news/.woodchuck.pid`)"; \
		echo "Web UI: http://localhost:8080"; \
	fi

# Stop Woodchuck News development server
stop-woodchuck-server:
	@echo "Stopping Woodchuck News server..."
	@if [ -f woodchuck-news/.woodchuck.pid ]; then \
		PID=`cat woodchuck-news/.woodchuck.pid`; \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID 2>/dev/null || true; \
			echo "Woodchuck News server stopped (PID: $$PID)"; \
		fi; \
		rm -f woodchuck-news/.woodchuck.pid; \
	fi
	@# Also kill any orphan http.server on port 8080
	@pkill -f "http.server 8080" 2>/dev/null || true
	@lsof -ti:8080 | xargs kill 2>/dev/null || true
	@echo "Woodchuck News server stopped"

# Check Woodchuck News server status
woodchuck-status:
	@if [ -f woodchuck-news/.woodchuck.pid ] && kill -0 `cat woodchuck-news/.woodchuck.pid` 2>/dev/null; then \
		echo "Woodchuck News server is running (PID: `cat woodchuck-news/.woodchuck.pid`)"; \
		echo "Web UI: http://localhost:8080"; \
	else \
		echo "Woodchuck News server is not running"; \
		if [ -f woodchuck-news/.woodchuck.pid ]; then \
			rm -f woodchuck-news/.woodchuck.pid; \
		fi; \
	fi

# ==================== Warmup & Cache ====================

# Check if cached output exists for today
check-cache:
	@$(UV) run python scripts/warmup.py --check

# Run warmup crawl (only if no cache exists)
warmup:
	@echo "🔥 Running warmup..."
	@$(UV) run python scripts/warmup.py

# Force warmup crawl (even if cache exists)
warmup-force:
	@echo "🔥 Running forced warmup..."
	@$(UV) run python scripts/warmup.py --force

# List platforms that will be crawled during warmup
warmup-list:
	@$(UV) run python scripts/warmup.py --list-platforms

# Start all services (Ollama + REST API + News Chat)
start-all: start-ollama start-rest-api start-news-chat
	@echo ""
	@echo "All services started!"
	@echo "  Ollama: http://localhost:11434"
	@echo "  REST API: http://localhost:3334"
	@echo "  News Chat: http://localhost:8000"

# Start all services with warmup (if no cache exists)
start-all-warmup: start-ollama start-rest-api
	@echo ""
	@echo "🔥 Checking cache and running warmup if needed..."
	@$(UV) run python scripts/warmup.py || true
	@$(MAKE) start-news-chat
	@echo ""
	@echo "All services started with warmup!"
	@echo "  Ollama: http://localhost:11434"
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
	@echo ""
	@echo "=== Woodchuck News (port 8080) ==="
	@$(MAKE) -s woodchuck-status

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
	rm -f woodchuck-news/.woodchuck.pid