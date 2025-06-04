import asyncio
import aiohttp
from typing import List, Dict, Any, Optional, Tuple
from langchain_mcp_adapters.client import MultiServerMCPClient
from config import settings


class MCPClientManager:
    """Manages MCP server discovery, health checking, and client initialization"""
    
    def __init__(self):
        self.working_servers: List[Dict[str, Any]] = []
        self.client: Optional[MultiServerMCPClient] = None
        self.tools: List[Any] = []
    
    async def check_server_health(self, server_info: Dict[str, Any], timeout: float = 5.0) -> bool:
        """Check if a single MCP server is healthy via its /health endpoint"""
        try:
            health_url = server_info.get("health_url")
            if not health_url:
                # Fallback to constructing health URL from base URL
                base_url = server_info["url"].replace("/mcp", "")
                health_url = f"{base_url}/health"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.get(health_url) as response:
                    if response.status == 200:
                        return True
                    else:
                        print(f"  ❌ {server_info['name'].title()}: Health check failed with status {response.status}")
                        return False
                        
        except asyncio.TimeoutError:
            print(f"  ❌ {server_info['name'].title()}: Health check timed out")
            return False
        except Exception as e:
            print(f"  ❌ {server_info['name'].title()}: Health check error: {e}")
            return False
    
    async def discover_working_servers(self) -> List[Dict[str, Any]]:
        """Discover which MCP servers are alive and working"""
        all_servers = settings.MCP_SERVERS
        
        if not all_servers:
            print("No MCP servers are configured. Please check your configuration.")
            return []
        
        print(f"🔍 Checking health of {len(all_servers)} configured MCP servers...")
        
        # Check health of all servers concurrently
        health_checks = [
            self.check_server_health(server) 
            for server in all_servers
        ]
        
        health_results = await asyncio.gather(*health_checks, return_exceptions=True)
        
        # Filter to only healthy servers
        working_servers = []
        for server, is_healthy in zip(all_servers, health_results):
            if isinstance(is_healthy, Exception):
                print(f"  ❌ {server['name'].title()}: Health check exception: {is_healthy}")
                continue
            
            if is_healthy:
                print(f"  ✅ {server['name'].title()}: Server is healthy")
                working_servers.append(server)
            else:
                print(f"  ❌ {server['name'].title()}: Server is not responding")
        
        self.working_servers = working_servers
        return working_servers
    
    async def test_server_tools(self, server_info: Dict[str, Any]) -> Dict[str, Any]:
        """Test if a single MCP server's tools can be fetched"""
        try:
            server_name = server_info["name"].title()
            server_config = {
                server_name: {
                    "url": server_info["url"],
                    "transport": "streamable_http",
                    "description": server_info["description"]
                }
            }
            
            # Test individual server
            client = MultiServerMCPClient(server_config)
            mcp_tools = await client.get_tools()
            
            return {
                "server": server_info,
                "status": "success",
                "tools_count": len(mcp_tools),
                "error": None
            }
            
        except Exception as e:
            return {
                "server": server_info,
                "status": "error", 
                "tools_count": 0,
                "error": str(e)
            }
    
    async def initialize_client(self) -> Tuple[Optional[MultiServerMCPClient], List[Any]]:
        """Initialize MCP client with working servers and fetch tools"""
        
        # First discover working servers
        working_servers = await self.discover_working_servers()
        
        if not working_servers:
            print("❌ No working MCP servers found. Please check your server configurations.")
            return None, []
        
        # Test tool fetching for each working server
        print(f"\n🔧 Testing tool fetching for {len(working_servers)} working servers...")
        tool_tests = [
            self.test_server_tools(server) 
            for server in working_servers
        ]
        
        test_results = await asyncio.gather(*tool_tests, return_exceptions=True)
        
        # Filter to servers that can provide tools
        functional_servers = []
        total_tools_expected = 0
        
        print("\n📊 Tool Test Results:")
        for result in test_results:
            if isinstance(result, Exception):
                print(f"  ❌ Tool test error: {result}")
                continue
                
            server_name = result["server"]["name"].title()
            if result["status"] == "success":
                print(f"  ✅ {server_name}: {result['tools_count']} tools available")
                functional_servers.append(result["server"])
                total_tools_expected += result["tools_count"]
            else:
                print(f"  ❌ {server_name}: {result['error']}")
        
        if not functional_servers:
            print("\n❌ No MCP servers can provide tools. Please check your server implementations.")
            return None, []
        
        print(f"\n✅ Found {len(functional_servers)} functional server(s) with {total_tools_expected} total tools")
        
        # Prepare server configuration for MultiServerMCPClient
        server_config = {}
        for server_info in functional_servers:
            server_name = server_info["name"].title()
            server_config[server_name] = {
                "url": server_info["url"],
                "transport": "streamable_http",
                "description": server_info["description"]
            }
            print(f"  - {server_name}: {server_info['url']}")
        
        # Create MultiServerMCPClient with functional servers
        try:
            client = MultiServerMCPClient(server_config)
            print(f"\n🔌 Fetching tools from {len(server_config)} functional MCP server(s)...")
            
            tools = await client.get_tools()
            
            if not tools:
                print("⚠️ No tools were fetched from functional MCP servers.")
                return client, []
            
            print(f"\n✅ Successfully fetched {len(tools)} tool(s) total:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
            
            self.client = client
            self.tools = tools
            return client, tools
            
        except Exception as e:
            print(f"❌ Error creating MCP client or fetching tools: {e}")
            
            # Add detailed error debugging
            print(f"Error type: {type(e).__name__}")
            if hasattr(e, '__cause__') and e.__cause__:
                print(f"Caused by: {e.__cause__}")
            
            import traceback
            print("Full traceback:")
            traceback.print_exc()
            return None, []
    
    async def get_client_and_tools(self) -> Tuple[Optional[MultiServerMCPClient], List[Any]]:
        """Get initialized client and tools, initializing if necessary"""
        if self.client is None or not self.tools:
            return await self.initialize_client()
        return self.client, self.tools


# Global instance for reuse
mcp_manager = MCPClientManager() 