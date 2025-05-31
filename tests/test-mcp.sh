#!/bin/bash

# MCP Connection Test Runner
# Convenient script to run MCP connection tests with common options

set -e

# Change to backend directory
cd "$(dirname "$0")/../backend"

echo "🧪 Running MCP Connection Tests"
echo "================================="

# Default command
PYTEST_CMD="uv run pytest ../tests/test_mcp_connection.py"

# Parse command line arguments
case "${1:-all}" in
    "all")
        echo "Running all tests..."
        $PYTEST_CMD -v
        ;;
    "fast")
        echo "Running fast tests (excluding slow tests)..."
        $PYTEST_CMD -m "not slow" -v
        ;;
    "health")
        echo "Running health check tests only..."
        $PYTEST_CMD::TestMCPServerHealth -v
        ;;
    "langchain")
        echo "Running LangChain integration tests only..."
        $PYTEST_CMD::TestLangChainMCPClient -v
        ;;
    "protocol")
        echo "Running raw MCP protocol tests only..."
        $PYTEST_CMD::TestMCPProtocol -v
        ;;
    "slow")
        echo "Running only slow tests..."
        $PYTEST_CMD -m "slow" -v
        ;;
    "verbose")
        echo "Running all tests with detailed output..."
        $PYTEST_CMD -v -s
        ;;
    *)
        echo "Usage: $0 [all|fast|health|langchain|protocol|slow|verbose]"
        echo ""
        echo "Options:"
        echo "  all       - Run all tests (default)"
        echo "  fast      - Run all tests except slow ones"
        echo "  health    - Run only health check tests"
        echo "  langchain - Run only LangChain integration tests"
        echo "  protocol  - Run only raw MCP protocol tests"
        echo "  slow      - Run only slow tests"
        echo "  verbose   - Run all tests with detailed output"
        exit 1
        ;;
esac

echo ""
echo "✅ Test run completed!" 