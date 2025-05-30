#!/usr/bin/env python3
"""
MCP Server Connection Test Script
Tests connectivity to all configured MCP servers using the same approach as agent.py.
"""

import asyncio
import sys
import aiohttp
from typing import Dict, Any, List
from src.nova.config import settings

# Import the same MCP client used in agent.py
try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    LANGCHAIN_MCP_AVAILABLE = True
except ImportError:
    print("⚠️  langchain-mcp-adapters not available. Install with: pip install langchain-mcp-adapters")
    LANGCHAIN_MCP_AVAILABLE = False


async def test_server_health(server_name: str, base_url: str) -> Dict[str, Any]:
    """Test if an MCP server is reachable and responding."""
    result = {
        "server": server_name,
        "url": base_url,
        "status": "unknown",
        "response_time": None,
        "error": None
    }
    
    try:
        # Remove '/mcp' or '/mcp/' from URL for health check
        health_url = base_url.rstrip('/').replace('/mcp', '') + '/health'
        
        start_time = asyncio.get_event_loop().time()
        async with aiohttp.ClientSession() as session:
            async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                end_time = asyncio.get_event_loop().time()
                result["response_time"] = round((end_time - start_time) * 1000, 2)  # ms
                
                if response.status == 200:
                    result["status"] = "healthy"
                else:
                    result["status"] = "unhealthy"
                    result["error"] = f"HTTP {response.status}"
                    
    except asyncio.TimeoutError:
        result["status"] = "timeout"
        result["error"] = "Connection timeout (5s)"
    except aiohttp.ClientConnectorError:
        result["status"] = "unreachable"
        result["error"] = "Connection refused - server not running?"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


async def test_mcp_tools_with_langchain_client() -> Dict[str, Any]:
    """Test MCP servers using the same MultiServerMCPClient as agent.py."""
    result = {
        "status": "unknown",
        "error": None,
        "servers_configured": 0,
        "servers_responding": 0,
        "tools_fetched": 0,
        "tools": []
    }
    
    if not LANGCHAIN_MCP_AVAILABLE:
        result["status"] = "error"
        result["error"] = "langchain-mcp-adapters not available"
        return result
    
    try:
        # Use the same server configuration approach as agent.py
        mcp_servers = settings.MCP_SERVERS
        result["servers_configured"] = len(mcp_servers)
        
        if not mcp_servers:
            result["status"] = "error"
            result["error"] = "No MCP servers configured"
            return result
        
        # Prepare server configuration for MultiServerMCPClient (same as agent.py)
        server_config = {}
        for server_info in mcp_servers:
            server_name = server_info["name"].title()
            server_config[server_name] = {
                "url": server_info["url"],
                "transport": "streamable_http",  # Use correct transport for HTTP servers
                "description": server_info["description"]
            }
        
        print(f"📋 Configured servers for MultiServerMCPClient:")
        for name, config in server_config.items():
            print(f"  • {name}: {config['url']}")
        
        # Create the MultiServerMCPClient (same as agent.py)
        print(f"\n🔗 Creating MultiServerMCPClient...")
        client = MultiServerMCPClient(server_config)
        
        # Fetch tools from all configured MCP servers (same as agent.py)
        print(f"🔍 Fetching tools using MultiServerMCPClient...")
        try:
            mcp_tools = await client.get_tools()
            print(f"✅ Successfully fetched {len(mcp_tools)} tools")
        except Exception as fetch_error:
            print(f"❌ Error during get_tools(): {fetch_error}")
            print(f"   Error type: {type(fetch_error).__name__}")
            
            # Try to get more details from the exception
            if hasattr(fetch_error, '__cause__') and fetch_error.__cause__:
                print(f"   Caused by: {fetch_error.__cause__}")
            if hasattr(fetch_error, 'exceptions'):
                print(f"   Sub-exceptions: {fetch_error.exceptions}")
            
            # Re-raise to be caught by outer try-except
            raise fetch_error
        
        result["status"] = "success"
        result["tools_fetched"] = len(mcp_tools)
        result["servers_responding"] = len([s for s in server_config.keys()])  # Assume all responding if tools fetched
        
        # Extract tool information for display
        for tool in mcp_tools:
            tool_info = {
                "name": tool.name,
                "description": tool.description,
                "args_schema": getattr(tool, 'args', {})
            }
            result["tools"].append(tool_info)
        
        print(f"✅ Successfully processed {len(mcp_tools)} tools from {len(server_config)} server(s)")
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"❌ Error using MultiServerMCPClient: {e}")
        print(f"   Error type: {type(e).__name__}")
        
        # Additional debugging information
        import traceback
        print(f"🔍 Full traceback:")
        traceback.print_exc()
    
    return result


async def test_individual_mcp_server(server_info: Dict[str, Any]) -> Dict[str, Any]:
    """Test a single MCP server individually to isolate issues."""
    result = {
        "server": server_info["name"],
        "status": "unknown",
        "error": None,
        "tools_fetched": 0,
        "tools": []
    }
    
    if not LANGCHAIN_MCP_AVAILABLE:
        result["status"] = "error"
        result["error"] = "langchain-mcp-adapters not available"
        return result
    
    try:
        # Test individual server
        server_name = server_info["name"].title()
        server_config = {
            server_name: {
                "url": server_info["url"],
                "transport": "streamable_http",
                "description": server_info["description"]
            }
        }
        
        print(f"🔍 Testing {server_name} individually...")
        print(f"  URL: {server_info['url']}")
        
        # Create client for just this server
        client = MultiServerMCPClient(server_config)
        
        # Fetch tools from this server
        mcp_tools = await client.get_tools()
        
        result["status"] = "success"
        result["tools_fetched"] = len(mcp_tools)
        
        # Extract tool information
        for tool in mcp_tools:
            tool_info = {
                "name": tool.name,
                "description": tool.description,
                "args_schema": getattr(tool, 'args', {})
            }
            result["tools"].append(tool_info)
        
        print(f"  ✅ Success: {len(mcp_tools)} tools fetched")
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  ❌ Error: {e}")
        
        # Check if it's a specific server error
        if "500 Internal Server Error" in str(e):
            print(f"  💡 Server {server_name} returned 500 error - MCP endpoint issue")
        elif "Connection refused" in str(e):
            print(f"  💡 Server {server_name} not running or unreachable")
    
    return result


async def main():
    """Main test function."""
    print("🔍 MCP Server Connection Test")
    print("=" * 50)
    print("Using the same approach as agent.py with MultiServerMCPClient")
    
    # Get configured servers from settings
    mcp_servers = settings.MCP_SERVERS
    
    if not mcp_servers:
        print("❌ No MCP servers configured in settings.MCP_SERVERS!")
        print("💡 Check your .env file and ensure MCP server URLs are set:")
        print("   - GMAIL_MCP_SERVER_URL")
        print("   - TASKS_MCP_SERVER_URL")
        sys.exit(1)
    
    print(f"📋 Found {len(mcp_servers)} configured MCP servers:")
    for server in mcp_servers:
        print(f"  • {server['name'].title()}: {server['url']}")
        print(f"    Description: {server['description']}")
    
    # Test 1: Health endpoints
    print("\n🏥 Testing server health endpoints...")
    health_tests = []
    for server in mcp_servers:
        health_tests.append(test_server_health(server["name"], server["url"]))
    
    health_results = await asyncio.gather(*health_tests, return_exceptions=True)
    
    print("\n📊 Health Check Results:")
    healthy_count = 0
    for result in health_results:
        if isinstance(result, Exception):
            print(f"  ❌ Error: {result}")
            continue
            
        status_emoji = {
            "healthy": "✅",
            "unhealthy": "⚠️", 
            "timeout": "⏰",
            "unreachable": "❌",
            "error": "💥"
        }.get(result["status"], "❓")
        
        print(f"  {status_emoji} {result['server'].title()}: {result['status']}")
        if result["response_time"]:
            print(f"    Response time: {result['response_time']}ms")
        if result["error"]:
            print(f"    Error: {result['error']}")
        if result["status"] == "healthy":
            healthy_count += 1

    # Test 2: Individual MCP server testing (NEW)
    print("\n🛠️  Testing MCP servers individually...")
    individual_results = []
    for server in mcp_servers:
        individual_result = await test_individual_mcp_server(server)
        individual_results.append(individual_result)
    
    print("\n📡 Individual MCP Server Results:")
    working_servers = 0
    total_tools = 0
    
    for result in individual_results:
        status_emoji = {
            "success": "✅",
            "error": "❌"
        }.get(result["status"], "❓")
        
        print(f"  {status_emoji} {result['server'].title()}: {result['status']}")
        
        if result["status"] == "success":
            print(f"    🛠️  Tools: {result['tools_fetched']}")
            working_servers += 1
            total_tools += result["tools_fetched"]
            
            if result["tools"]:
                for tool in result["tools"]:
                    print(f"      - {tool['name']}: {tool['description']}")
        else:
            print(f"    ❌ Error: {result['error']}")

    # Test 3: Combined MCP Tools (only if individual tests show some working servers)
    if working_servers > 0:
        print(f"\n🔗 Testing combined MultiServerMCPClient (all servers)...")
        tools_result = await test_mcp_tools_with_langchain_client()
        
        if tools_result["status"] == "success":
            print(f"  ✅ Combined test successful: {tools_result['tools_fetched']} total tools")
        else:
            print(f"  ❌ Combined test failed: {tools_result['error']}")
            print(f"  💡 Individual servers work but combined connection fails")
    else:
        print(f"\n⚠️  Skipping combined test - no individual servers working")
        tools_result = {"status": "skipped", "tools_fetched": 0}
    
    # Summary
    print(f"\n📈 Summary:")
    print(f"  • Total servers configured: {len(mcp_servers)}")
    print(f"  • Health check passed: {healthy_count}/{len(mcp_servers)}")
    print(f"  • Individual MCP servers working: {working_servers}/{len(mcp_servers)}")
    print(f"  • Total tools available: {total_tools}")
    
    # Focus on Gmail server results
    gmail_result = next((r for r in individual_results if r["server"] == "gmail"), None)
    if gmail_result:
        print(f"\n📧 Gmail MCP Server Focus:")
        print(f"  • Status: {'✅' if gmail_result['status'] == 'success' else '❌'} {gmail_result['status']}")
        if gmail_result["status"] == "success":
            print(f"  • Tools available: {gmail_result['tools_fetched']}")
            if gmail_result["tools"]:
                print(f"  • Available tools:")
                for tool in gmail_result["tools"]:
                    print(f"    - {tool['name']}")
        else:
            print(f"  • Error: {gmail_result['error']}")
            print(f"  💡 Check Gmail MCP server at port 8001")
    
    # Exit codes
    if gmail_result and gmail_result["status"] == "success":
        print(f"\n🎉 Gmail MCP server is working correctly!")
        if working_servers == len(mcp_servers):
            print(f"🎉 All MCP servers working!")
            sys.exit(0)
        else:
            print(f"⚠️  Some servers need fixes")
            sys.exit(0)  # Exit successfully if Gmail works
    else:
        print(f"\n❌ Gmail MCP server needs fixing")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 