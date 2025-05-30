#!/usr/bin/env python3
"""
MCP Server Connection Test Script
Tests connectivity to all configured MCP servers.
"""

import asyncio
import sys
import aiohttp
from typing import Dict, Any
from src.nova.config import settings


async def test_server_health(server_name: str, url: str) -> Dict[str, Any]:
    """Test if an MCP server is reachable and responding."""
    result = {
        "server": server_name,
        "url": url,
        "status": "unknown",
        "response_time": None,
        "error": None
    }
    
    try:
        # Remove '/mcp' or '/mcp/' from URL for health check
        health_url = url.rstrip('/').replace('/mcp', '') + '/health'
        
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


async def test_mcp_endpoint(server_name: str, url: str) -> Dict[str, Any]:
    """Test the MCP endpoint directly."""
    result = {
        "server": server_name,
        "url": url,
        "status": "unknown",
        "error": None,
        "tools_available": False,
        "tool_count": 0
    }
    
    try:
        # All MCP URLs now use trailing slash consistently
        
        # Test MCP initialization request with FastMCP headers
        mcp_payload = {
            "jsonrpc": "2.0",
            "method": "initialize", 
            "params": {
                "protocolVersion": 1,
                "capabilities": {},
                "clientInfo": {
                    "name": "TestClient",
                    "version": "1.0.0"
                }
            },
            "id": "test-init"
        }
        
        # FastMCP requires SSE-compatible headers
        fastmcp_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        
        async with aiohttp.ClientSession() as session:
            # Step 1: Initialize
            async with session.post(
                url,
                json=mcp_payload,
                headers=fastmcp_headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                if response.status == 200:
                    # Extract session ID from headers
                    session_id = response.headers.get('mcp-session-id')
                    response_text = await response.text()
                    
                    if session_id and ("initialize" in response_text or "event: message" in response_text):
                        result["status"] = "responding"
                        
                        # Step 2: Send notifications/initialized with session ID
                        notif_headers = fastmcp_headers.copy()
                        notif_headers["Mcp-Session-Id"] = session_id
                        
                        notif_payload = {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                            "params": {}
                        }
                        
                        async with session.post(
                            url,
                            json=notif_payload,
                            headers=notif_headers,
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as notif_response:
                            
                            # Step 3: Try to get tools list
                            tools_payload = {
                                "jsonrpc": "2.0",
                                "method": "tools/list",
                                "params": {},
                                "id": "test-tools"
                            }
                            
                            async with session.post(
                                url,
                                json=tools_payload,
                                headers=notif_headers,
                                timeout=aiohttp.ClientTimeout(total=5)
                            ) as tools_response:
                                
                                if tools_response.status == 200:
                                    tools_text = await tools_response.text()
                                    try:
                                        # FastMCP might return direct JSON for tools/list
                                        tools_data = await tools_response.json()
                                        if "result" in tools_data and isinstance(tools_data["result"], list):
                                            result["tools_available"] = True
                                            result["tool_count"] = len(tools_data["result"])
                                    except:
                                        # Or it might be in SSE format
                                        if "tools" in tools_text or "result" in tools_text:
                                            result["tools_available"] = True
                                            # Try to count tools from SSE response
                                            if '"tools"' in tools_text:
                                                import re
                                                tool_matches = re.findall(r'"name":', tools_text)
                                                result["tool_count"] = len(tool_matches)
                    else:
                        result["status"] = "error"
                        result["error"] = "No session ID or invalid initialization response"
                        
                else:
                    result["status"] = "error"
                    result["error"] = f"HTTP {response.status}"
                    
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


async def main():
    """Main test function."""
    print("🔍 MCP Server Connection Test")
    print("=" * 50)
    
    # Get configured servers
    active_servers = settings.active_mcp_servers
    
    if not active_servers:
        print("❌ No MCP servers configured!")
        sys.exit(1)
    
    print(f"📋 Found {len(active_servers)} configured MCP servers:")
    for name, info in active_servers.items():
        print(f"  • {name.title()}: {info['url']}")
    
    print("\n🏥 Testing server health endpoints...")
    health_tests = []
    for name, info in active_servers.items():
        if info["url"]:
            health_tests.append(test_server_health(name, info["url"]))
    
    health_results = await asyncio.gather(*health_tests, return_exceptions=True)
    
    print("\n📊 Health Check Results:")
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
    
    print("\n🔌 Testing MCP endpoints...")
    mcp_tests = []
    for name, info in active_servers.items():
        if info["url"]:
            mcp_tests.append(test_mcp_endpoint(name, info["url"]))
    
    mcp_results = await asyncio.gather(*mcp_tests, return_exceptions=True)
    
    print("\n📡 MCP Endpoint Results:")
    total_tools = 0
    working_servers = 0
    
    for result in mcp_results:
        if isinstance(result, Exception):
            print(f"  ❌ Error: {result}")
            continue
        
        status_emoji = {
            "responding": "✅",
            "error": "❌", 
            "unknown": "❓"
        }.get(result["status"], "❓")
        
        print(f"  {status_emoji} {result['server'].title()}: {result['status']}")
        
        if result["tools_available"]:
            print(f"    🛠️  Tools available: {result['tool_count']}")
            total_tools += result["tool_count"]
            working_servers += 1
        elif result["status"] == "responding":
            print(f"    ⚠️  No tools found")
        
        if result["error"]:
            print(f"    ❌ Error: {result['error']}")
    
    print(f"\n📈 Summary:")
    print(f"  • Total servers configured: {len(active_servers)}")
    print(f"  • Working MCP servers: {working_servers}")
    print(f"  • Total tools available: {total_tools}")
    
    # Special focus on tasks server
    tasks_info = active_servers.get("tasks")
    if tasks_info:
        print(f"\n🎯 Tasks MCP Server (Port 8002):")
        print(f"  • URL: {tasks_info['url']}")
        
        tasks_result = next((r for r in mcp_results if isinstance(r, dict) and r["server"] == "tasks"), None)
        if tasks_result:
            if tasks_result["status"] == "responding":
                print(f"  • Status: ✅ Connected successfully!")
                if tasks_result["tools_available"]:
                    print(f"  • Tools: {tasks_result['tool_count']} available")
                else:
                    print(f"  • Tools: ⚠️  None found")
            else:
                print(f"  • Status: ❌ {tasks_result['status']}")
                if tasks_result["error"]:
                    print(f"  • Error: {tasks_result['error']}")
                print(f"  • 💡 Make sure the tasks.md server is running on port 8002")
    
    if working_servers == 0:
        print(f"\n⚠️  No MCP servers are responding!")
        print(f"   Please ensure your MCP servers are running.")
        sys.exit(1)
    elif working_servers < len(active_servers):
        print(f"\n⚠️  {len(active_servers) - working_servers} server(s) not responding.")
        sys.exit(1)
    else:
        print(f"\n🎉 All MCP servers are responding correctly!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main()) 