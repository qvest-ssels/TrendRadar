#!/bin/bash
# Local development script for Woodchuck News Generator
# Runs the generator locally and serves with Python's HTTP server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🦫 Woodchuck News - Local Development${NC}"
echo ""

# Create output directory
mkdir -p output

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q -r generator/requirements.txt

# Set environment variables for local development
export MCP_API_URL="${MCP_API_URL:-http://localhost:3333}"
export OUTPUT_DIR="$SCRIPT_DIR/output"
export TEMPLATES_DIR="$SCRIPT_DIR/templates"
export STATIC_DIR="$SCRIPT_DIR/static"

# Run the generator
echo -e "${YELLOW}Running generator...${NC}"
python -m generator.generator "$@"

# Copy static files
echo -e "${YELLOW}Copying static files...${NC}"
cp -r static/* output/ 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ Generation complete!${NC}"
echo ""
echo "To serve locally, run:"
echo "  cd output && python -m http.server 8080"
echo ""
echo "Then open: http://localhost:8080"
