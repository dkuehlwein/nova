#!/usr/bin/env python3
"""
Feature Request MCP Server

An MCP server that allows Nova to create and manage feature requests in Linear
when she encounters limitations or needs new capabilities.
"""

import os
from dotenv import load_dotenv
from fastmcp import FastMCP

from src.linear_client import LinearClient
from src.feature_analyzer import FeatureRequestAnalyzer
from src.mcp_tools import create_request_feature_tool
from src.llm_factory import validate_configuration

# Load environment variables
load_dotenv()

# Configuration
LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")
LINEAR_API_URL = os.getenv("LINEAR_API_URL", "https://api.linear.app/graphql")
ANALYZER_MODEL_NAME = os.getenv("ANALYZER_MODEL_NAME", "gemini-3-flash-preview")

# Validate LiteLLM configuration
litellm_config = validate_configuration()

# Initialize FastMCP server
mcp = FastMCP(name="FeatureRequestServer")

# Initialize clients (only if API keys are available)
linear_client = None
analyzer = None

if LINEAR_API_KEY and litellm_config["valid"]:
    linear_client = LinearClient(LINEAR_API_KEY, LINEAR_API_URL)
    analyzer = FeatureRequestAnalyzer(ANALYZER_MODEL_NAME)
    print("✅ Feature request system fully configured and ready")
else:
    print("⚠️  Feature request system partially configured:")
    if not LINEAR_API_KEY:
        print("   - Missing Linear API key (service will not function)")
    if not litellm_config["valid"]:
        print("   - Invalid LiteLLM configuration (AI analysis will not work)")

# Register the request_feature tool
request_feature = create_request_feature_tool(mcp, linear_client, analyzer)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Feature Request MCP Server')
    parser.add_argument('--host', default=os.getenv('HOST', '127.0.0.1'), help='Host to bind the server to')
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT', '8003')), help='Port to bind the server to')
    
    args = parser.parse_args()
    
    print(f"Starting Feature Request MCP server on http://{args.host}:{args.port}")
    print(f"MCP endpoint: http://{args.host}:{args.port}/mcp")
    
    # Configuration status
    if not LINEAR_API_KEY:
        print("❌ LINEAR_API_KEY not configured - REQUIRED for feature request functionality")
        print("   Without Linear API access, the service cannot create or update issues")
    else:
        print("✅ Linear API configured")
    
    if not litellm_config["valid"]:
        print(f"❌ LiteLLM configuration FAILED: {litellm_config.get('error', 'Unknown error')}")
        print("🔧 To fix this:")
        print("   1. Generate a virtual key: python scripts/generate_feature_request_key.py")
        print("   2. Set FEATURE_REQUEST_LITELLM_KEY in your environment")
        print("   3. Restart the service")
        print("\n⚠️  Service will not function without a dedicated virtual key!")
    else:
        print(f"✅ LiteLLM configured: {litellm_config['base_url']}")
        print(f"🔒 Using dedicated service API key: {litellm_config.get('service_key_prefix', 'unknown')}")
        print(f"📊 Available models: {', '.join(litellm_config['available_models'])}")
    
    # Run the server
    mcp.run(transport="streamable-http", host=args.host, port=args.port, path="/mcp") 