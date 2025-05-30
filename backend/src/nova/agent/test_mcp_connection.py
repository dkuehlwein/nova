#!/usr/bin/env python3
"""
MCP Server Connection Test Script
Tests connectivity to all configured MCP servers using the same approach as agent.py.
"""

import asyncio
import sys
import aiohttp
import json
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
                    try:
                        health_data = await response.json()
                        print(f"  📊 Health response: {json.dumps(health_data, indent=2)}")
                    except:
                        pass
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


async def test_raw_mcp_protocol(server_info: Dict[str, Any]) -> Dict[str, Any]:
    """Test MCP server using raw JSON-RPC protocol to debug tool descriptions."""
    result = {
        "server": server_info["name"],
        "status": "unknown",
        "error": None,
        "tools": [],
        "raw_responses": {}
    }
    
    try:
        base_url = server_info["url"].rstrip('/')
        
        print(f"\n🔬 Testing {server_info['name']} with raw MCP protocol...")
        print(f"  URL: {base_url}")
        
        async with aiohttp.ClientSession() as session:
            # Test tools/list request
            list_tools_request = {
                "jsonrpc": "2.0",
                "id": "test-list-tools",
                "method": "tools/list",
                "params": {}
            }
            
            print(f"  📤 Sending tools/list request...")
            async with session.post(
                base_url,
                json=list_tools_request,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response_text = await response.text()
                print(f"  📥 Response status: {response.status}")
                print(f"  📥 Response text: {response_text[:500]}...")
                
                if response.status == 200:
                    try:
                        response_data = json.loads(response_text)
                        result["raw_responses"]["tools_list"] = response_data
                        
                        if "result" in response_data and "tools" in response_data["result"]:
                            tools = response_data["result"]["tools"]
                            result["tools"] = tools
                            result["status"] = "success"
                            
                            print(f"  ✅ Found {len(tools)} tools:")
                            for i, tool in enumerate(tools):
                                print(f"    {i+1}. {tool.get('name', 'UNNAMED')}")
                                print(f"       Description: '{tool.get('description', 'NO DESCRIPTION')}'")
                                print(f"       Schema: {json.dumps(tool.get('inputSchema', {}), indent=6)}")
                        else:
                            result["status"] = "error"
                            result["error"] = f"Unexpected response format: {response_data}"
                    except json.JSONDecodeError as e:
                        result["status"] = "error"
                        result["error"] = f"Invalid JSON response: {e}"
                else:
                    result["status"] = "error"
                    result["error"] = f"HTTP {response.status}: {response_text}"
            
            # Test a simple tool call if we found tools
            if result["status"] == "success" and result["tools"]:
                # Try to call list_tasks if it exists
                list_task_tool = next((t for t in result["tools"] if t.get('name') == 'list_tasks'), None)
                if list_task_tool:
                    print(f"  🧪 Testing list_tasks tool call...")
                    
                    call_tool_request = {
                        "jsonrpc": "2.0",
                        "id": "test-call-tool",
                        "method": "tools/call",
                        "params": {
                            "name": "list_tasks",
                            "arguments": {}
                        }
                    }
                    
                    async with session.post(
                        base_url,
                        json=call_tool_request,
                        headers={"Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as call_response:
                        call_response_text = await call_response.text()
                        print(f"    📥 Call response status: {call_response.status}")
                        print(f"    📥 Call response: {call_response_text[:300]}...")
                        
                        if call_response.status == 200:
                            try:
                                call_data = json.loads(call_response_text)
                                result["raw_responses"]["tool_call"] = call_data
                                print(f"    ✅ Tool call successful!")
                            except json.JSONDecodeError:
                                print(f"    ❌ Tool call returned invalid JSON")
                        else:
                            print(f"    ❌ Tool call failed: HTTP {call_response.status}")
                            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  ❌ Raw protocol test failed: {e}")
    
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
        
        print(f"\n📋 Configured servers for MultiServerMCPClient:")
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
            
            # Detailed tool analysis
            print(f"\n🔬 Detailed tool analysis:")
            for i, tool in enumerate(mcp_tools):
                print(f"  {i+1}. {tool.name}")
                print(f"     Description: '{tool.description}'")
                print(f"     Type: {type(tool)}")
                
                # Try to access tool schema/args
                if hasattr(tool, 'args'):
                    print(f"     Args schema: {tool.args}")
                if hasattr(tool, 'args_schema'): 
                    print(f"     Args schema (alt): {tool.args_schema}")
                if hasattr(tool, 'schema'):
                    print(f"     Schema: {tool.schema}")
                if hasattr(tool, '__dict__'):
                    print(f"     All attributes: {list(tool.__dict__.keys())}")
                    
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
        print(f"  ❌ Failed: {e}")
    
    return result


async def main():
    """Main test function."""
    print("🚀 MCP Server Connection Test")
    print("=" * 50)
    
    # Get configured MCP servers
    mcp_servers = settings.MCP_SERVERS
    print(f"📡 Found {len(mcp_servers)} configured MCP server(s):")
    for server in mcp_servers:
        print(f"  • {server['name']}: {server['url']}")
    
    if not mcp_servers:
        print("❌ No MCP servers configured. Check your .env file.")
        return
    
    print("\n" + "=" * 50)
    print("🏥 HEALTH CHECK TESTS")
    print("=" * 50)
    
    # Test server health
    health_results = []
    for server in mcp_servers:
        print(f"\n🔍 Testing {server['name']} health...")
        health_result = await test_server_health(server['name'], server['url'])
        health_results.append(health_result)
        
        status_emoji = {
            "healthy": "✅",
            "unhealthy": "⚠️",
            "timeout": "⏰",
            "unreachable": "❌",
            "error": "💥"
        }.get(health_result["status"], "❓")
        
        print(f"  {status_emoji} Status: {health_result['status']}")
        if health_result["response_time"]:
            print(f"  ⏱️  Response time: {health_result['response_time']}ms")
        if health_result["error"]:
            print(f"  ❌ Error: {health_result['error']}")
    
    print("\n" + "=" * 50)
    print("🔬 RAW MCP PROTOCOL TESTS")
    print("=" * 50)
    
    # Test raw MCP protocol for each server
    for server in mcp_servers:
        await test_raw_mcp_protocol(server)
    
    print("\n" + "=" * 50)
    print("🔗 LANGCHAIN MCP CLIENT TESTS")
    print("=" * 50)
    
    # Test with LangChain MCP client (what agent.py uses)
    if LANGCHAIN_MCP_AVAILABLE:
        langchain_result = await test_mcp_tools_with_langchain_client()
        
        if langchain_result["status"] == "success":
            print(f"\n📊 Summary:")
            print(f"  • Servers configured: {langchain_result['servers_configured']}")
            print(f"  • Servers responding: {langchain_result['servers_responding']}")
            print(f"  • Tools fetched: {langchain_result['tools_fetched']}")
            
            print(f"\n🛠️  Tool Details:")
            for tool in langchain_result["tools"]:
                print(f"  • {tool['name']}: {tool['description'][:50]}...")
        else:
            print(f"❌ LangChain MCP client test failed: {langchain_result['error']}")
        
        # Test individual servers for isolation
        print(f"\n🔍 Individual server tests:")
        for server in mcp_servers:
            individual_result = await test_individual_mcp_server(server)
            status_emoji = "✅" if individual_result["status"] == "success" else "❌"
            print(f"  {status_emoji} {server['name']}: {individual_result['tools_fetched']} tools")
            if individual_result["error"]:
                print(f"    Error: {individual_result['error']}")
    else:
        print("⚠️  Skipping LangChain tests - package not available")
    
    print("\n" + "=" * 50)
    print("✅ Test completed!")


if __name__ == "__main__":
    asyncio.run(main()) 