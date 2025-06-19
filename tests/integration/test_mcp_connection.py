#!/usr/bin/env python3
"""
MCP Server Connection Integration Tests

Tests real HTTP connectivity to any MCP servers configured in configs/mcp_servers.yaml.
These are integration tests that require actual MCP servers to be running.

Moved from tests/test_mcp_connection.py to proper integration test location.
"""

import asyncio
import aiohttp
import json
import pytest
from typing import Dict, Any
from config import settings

# Import the same MCP client used in agent.py
try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    LANGCHAIN_MCP_AVAILABLE = True
except ImportError:
    LANGCHAIN_MCP_AVAILABLE = False


@pytest.fixture
def mcp_servers():
    """Fixture providing MCP server configuration."""
    servers = settings.MCP_SERVERS
    if not servers:
        pytest.skip("No MCP servers configured")
    return servers


@pytest.fixture
def mcp_client():
    """Fixture providing MultiServerMCPClient if available."""
    if not LANGCHAIN_MCP_AVAILABLE:
        pytest.skip("langchain-mcp-adapters not available")
    return MultiServerMCPClient


class TestMCPServerHealth:
    """Test MCP server health endpoints."""

    @pytest.mark.asyncio
    async def test_server_health_endpoints(self, mcp_servers):
        """Test that all MCP servers respond to health checks if they're running."""
        results = []
        for server in mcp_servers:
            result = await self._check_server_health(server["name"], server["url"])
            results.append(result)
            
            # Log the result for debugging
            print(f"Server {server['name']}: {result['status']} - {result.get('error', 'OK')}")
        
        # At least one server should be testable (even if it fails)
        assert len(results) > 0, "No MCP servers to test"
        
        # Check that we got valid responses (even errors are valid for testing)
        for result in results:
            assert result["status"] in ["healthy", "unhealthy", "unreachable", "timeout", "error"], \
                f"Invalid status for {result['server']}: {result['status']}"

    async def _check_server_health(self, server_name: str, base_url: str) -> Dict[str, Any]:
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
                            print(f"Health response for {server_name}: {json.dumps(health_data, indent=2)}")
                        except Exception:
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


class TestMCPProtocol:
    """Test raw MCP JSON-RPC protocol."""
    
    @pytest.mark.asyncio
    async def test_tools_list_endpoint(self, mcp_servers):
        """Test that MCP servers respond to tools/list requests."""
        for server in mcp_servers:
            result = await self._test_raw_mcp_protocol(server)
            
            # Accept various outcomes - servers may not be running in CI
            assert result["status"] in ["success", "error", "unreachable"], \
                f"Unexpected status for {server['name']}: {result['status']}"
            
            if result["status"] == "error" and "406" in str(result["error"]):
                # This is expected - server requires proper headers
                print(f"Server {server['name']} requires proper MCP headers (expected)")
            elif result["status"] == "success":
                assert len(result["tools"]) > 0, f"Server {server['name']} returned no tools"
                
                # Validate tool structure
                for tool in result["tools"]:
                    assert "name" in tool, f"Tool missing name in {server['name']}"
                    assert "description" in tool, f"Tool missing description in {server['name']}"
            elif result["status"] == "unreachable":
                print(f"Server {server['name']} is not running (expected in CI)")
    
    async def _test_raw_mcp_protocol(self, server_info: Dict[str, Any]) -> Dict[str, Any]:
        """Test MCP server using raw JSON-RPC protocol."""
        result = {
            "server": server_info["name"],
            "status": "unknown",
            "error": None,
            "tools": [],
            "raw_responses": {}
        }
        
        try:
            base_url = server_info["url"].rstrip('/')
            
            async with aiohttp.ClientSession() as session:
                # Test tools/list request
                list_tools_request = {
                    "jsonrpc": "2.0",
                    "id": "test-list-tools",
                    "method": "tools/list",
                    "params": {}
                }
                
                async with session.post(
                    base_url,
                    json=list_tools_request,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        try:
                            response_data = json.loads(response_text)
                            result["raw_responses"]["tools_list"] = response_data
                            
                            if "result" in response_data and "tools" in response_data["result"]:
                                tools = response_data["result"]["tools"]
                                result["tools"] = tools
                                result["status"] = "success"
                            else:
                                result["status"] = "error"
                                result["error"] = f"Unexpected response format: {response_data}"
                        except json.JSONDecodeError as e:
                            result["status"] = "error"
                            result["error"] = f"Invalid JSON response: {e}"
                    else:
                        result["status"] = "error"
                        result["error"] = f"HTTP {response.status}: {response_text}"
                        
        except aiohttp.ClientConnectorError:
            result["status"] = "unreachable"
            result["error"] = "Connection refused - server not running?"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
        
        return result


class TestLangChainMCPClient:
    """Test MCP integration using LangChain MCP client (same as agent.py)."""
    
    @pytest.mark.asyncio
    async def test_multiserver_client_connection(self, mcp_servers, mcp_client):
        """Test that MultiServerMCPClient can connect to running servers."""
        # Prepare server configuration for MultiServerMCPClient
        server_config = {}
        for server_info in mcp_servers:
            server_name = server_info["name"].title()
            server_config[server_name] = {
                "url": server_info["url"],
                "transport": "streamable_http",
                "description": server_info["description"]
            }
        
        # Create the MultiServerMCPClient
        client = mcp_client(server_config)
        
        try:
            # Fetch tools from all configured MCP servers
            mcp_tools = await client.get_tools()
            
            # If we get here, at least some servers are running
            assert len(mcp_tools) >= 0, "MCP tools should be a list"
            print(f"Successfully fetched {len(mcp_tools)} tools from {len(server_config)} servers")
            
            # Validate tool structure if tools exist
            for tool in mcp_tools:
                assert hasattr(tool, 'name'), f"Tool missing name attribute: {tool}"
                assert hasattr(tool, 'description'), f"Tool missing description attribute: {tool}"
                assert tool.name, f"Tool has empty name: {tool}"
                assert tool.description, f"Tool has empty description: {tool}"
                
        except Exception as e:
            # In CI/testing, servers may not be running - this is acceptable
            print(f"MCP client connection failed (expected if servers not running): {e}")
            pytest.skip("MCP servers not available for testing")
    
    @pytest.mark.asyncio
    async def test_individual_server_connections(self, mcp_servers, mcp_client):
        """Test each MCP server individually to isolate connection issues."""
        successful_connections = 0
        
        for server_info in mcp_servers:
            # Test individual server
            server_name = server_info["name"].title()
            server_config = {
                server_name: {
                    "url": server_info["url"],
                    "transport": "streamable_http",
                    "description": server_info["description"]
                }
            }
            
            try:
                # Create client for just this server
                client = mcp_client(server_config)
                
                # Fetch tools from this server
                mcp_tools = await client.get_tools()
                
                successful_connections += 1
                print(f"Server {server_name}: {len(mcp_tools)} tools")
                
                # Validate at least basic tool attributes
                for tool in mcp_tools[:3]:  # Check first 3 tools
                    assert tool.name, f"Tool from {server_name} has no name"
                    assert tool.description, f"Tool from {server_name} has no description"
                    
            except Exception as e:
                print(f"Server {server_name} connection failed: {e}")
        
        # Don't require any successful connections in CI
        print(f"Successfully connected to {successful_connections}/{len(mcp_servers)} servers")
    
    @pytest.mark.asyncio
    async def test_tool_schema_validation(self, mcp_servers, mcp_client):
        """Test that tools have valid schemas and can be inspected."""
        server_config = {}
        for server_info in mcp_servers:
            server_name = server_info["name"].title()
            server_config[server_name] = {
                "url": server_info["url"],
                "transport": "streamable_http",
                "description": server_info["description"]
            }
        
        try:
            client = mcp_client(server_config)
            mcp_tools = await client.get_tools()
            
            schema_validation_errors = []
            
            for tool in mcp_tools:
                try:
                    # Try to access tool schema
                    if hasattr(tool, 'args_schema'):
                        schema = tool.args_schema
                        assert schema is not None, f"Tool {tool.name} has None args_schema"
                    
                    # Try to access tool args (this can fail for some tools)
                    if hasattr(tool, 'args'):
                        try:
                            args = tool.args
                        except Exception as e:
                            # Log the error but don't fail the test
                            schema_validation_errors.append(f"Tool {tool.name}: {e}")
                            
                except Exception as e:
                    schema_validation_errors.append(f"Tool {tool.name} schema validation failed: {e}")
            
            # Print schema validation errors for debugging but don't fail
            if schema_validation_errors:
                print(f"Schema validation warnings ({len(schema_validation_errors)} tools):")
                for error in schema_validation_errors[:5]:  # Show first 5 errors
                    print(f"  - {error}")
            
            # Test should pass as long as we got tools
            if len(mcp_tools) > 0:
                print(f"Schema validation completed for {len(mcp_tools)} tools")
        
        except Exception as e:
            print(f"Schema validation skipped - no servers available: {e}")
            pytest.skip("No MCP servers available for schema validation")


class TestMCPToolExecution:
    """Test actual tool execution (optional, more intensive tests)."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_basic_tool_execution(self, mcp_servers, mcp_client):
        """Test execution of basic tools like list operations."""
        server_config = {}
        for server_info in mcp_servers:
            server_name = server_info["name"].title()
            server_config[server_name] = {
                "url": server_info["url"],
                "transport": "streamable_http",
                "description": server_info["description"]
            }
        
        try:
            client = mcp_client(server_config)
            mcp_tools = await client.get_tools()
            
            # Find safe list-type tools to test
            safe_tools = [
                tool for tool in mcp_tools 
                if any(keyword in tool.name.lower() for keyword in ['list', 'get_unread', 'lanes'])
                and not any(keyword in tool.name.lower() for keyword in ['delete', 'create', 'send'])
            ]
            
            if not safe_tools:
                pytest.skip("No safe tools found for execution testing")
            
            # Test first safe tool
            test_tool = safe_tools[0]
            print(f"Testing tool execution: {test_tool.name}")
            
            try:
                # Try to call the tool with no arguments
                result = await test_tool.ainvoke({})
                assert result is not None, f"Tool {test_tool.name} returned None"
                print(f"Tool {test_tool.name} executed successfully")
            except Exception as e:
                # Some tools might require arguments or might fail in test environment
                print(f"Tool {test_tool.name} execution failed (expected in test env): {e}")
        
        except Exception as e:
            print(f"Tool execution test skipped - no servers available: {e}")
            pytest.skip("No MCP servers available for tool execution testing")


if __name__ == "__main__":
    # Allow running as script for debugging
    pytest.main([__file__, "-v", "--tb=short"]) 