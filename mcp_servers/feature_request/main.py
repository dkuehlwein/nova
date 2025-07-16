#!/usr/bin/env python3
"""
Feature Request MCP Server

An MCP server that allows Nova to create and manage feature requests in Linear
when she encounters limitations or needs new capabilities.
"""

import os
from dotenv import load_dotenv
import google.generativeai as genai
from fastmcp import FastMCP

from src.linear_client import LinearClient
from src.feature_analyzer import FeatureRequestAnalyzer
from src.mcp_tools import create_request_feature_tool

# Load environment variables
load_dotenv()

# Configuration
LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") 
LINEAR_API_URL = os.getenv("LINEAR_API_URL", "https://api.linear.app/graphql")
GOOGLE_MODEL_NAME = os.getenv("GOOGLE_MODEL_NAME", "gemini-2.5-flash")

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Initialize FastMCP server
mcp = FastMCP(name="FeatureRequestServer")

# Initialize clients (only if API keys are available)
linear_client = None
analyzer = None

if LINEAR_API_KEY and GEMINI_API_KEY:
    linear_client = LinearClient(LINEAR_API_KEY, LINEAR_API_URL)
    analyzer = FeatureRequestAnalyzer(GOOGLE_MODEL_NAME)

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
    
    if not LINEAR_API_KEY:
        print("WARNING: LINEAR_API_KEY not configured")
    if not GEMINI_API_KEY:
        print("WARNING: GOOGLE_API_KEY not configured")
    
    # Run the server
    mcp.run(transport="streamable-http", host=args.host, port=args.port, path="/mcp") 