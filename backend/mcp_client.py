import asyncio
from typing import List, Dict, Any, Optional, Tuple
from langchain_mcp_adapters.client import MultiServerMCPClient
from config import settings
from utils.logging import get_logger

logger = get_logger("mcp-client")


class MCPClientManager:
    """Manages MCP server discovery, health checking, and client initialization"""
    
    def __init__(self):
        self.working_servers: List[Dict[str, Any]] = []
        self.client: Optional[MultiServerMCPClient] = None
        self.tools: List[Any] = []
    
    async def check_server_health_and_get_tools_count(self, server_info: Dict[str, Any], timeout: float = 5.0) -> Tuple[bool, Optional[int]]:
        """Check server health and get tools count using standard MCP tools/list endpoint"""
        server_name = server_info.get("name", "unknown")
        
        try:
            # Use the MCP client to list tools from this specific server
            server_config = {
                server_name: {
                    "url": server_info["url"],
                    "transport": "streamable_http",
                    "description": server_info["description"]
                }
            }
            
            # Create a temporary client for this specific server
            client = MultiServerMCPClient(server_config)
            
            # Try to get tools - this tests both health and gives us tools count
            tools = await asyncio.wait_for(client.get_tools(), timeout=timeout)
            tools_count = len(tools)
            
            logger.debug(f"MCP server {server_name}: healthy=True, tools_count={tools_count}")
            return True, tools_count
            
        except asyncio.TimeoutError:
            logger.warning(f"MCP tools/list timeout for {server_name}")
            return False, None
        except Exception as e:
            logger.warning(f"MCP tools/list failed for {server_name}: {e}")
            return False, None

    async def discover_working_servers(self) -> List[Dict[str, Any]]:
        """Discover which MCP servers are alive and working"""
        all_servers = settings.MCP_SERVERS
        
        if not all_servers:
            logger.warning("No MCP servers configured")
            return []
        
        logger.info(f"Checking health of {len(all_servers)} MCP servers")
        
        # Check health of all servers concurrently
        health_checks = [
            self.check_server_health_and_get_tools_count(server) 
            for server in all_servers
        ]
        
        health_results = await asyncio.gather(*health_checks, return_exceptions=True)
        
        # Filter to only healthy servers
        working_servers = []
        failed_servers = []
        for server, result in zip(all_servers, health_results):
            server_name = server.get("name", "unknown")
            if isinstance(result, Exception):
                failed_servers.append({
                    "name": server_name,
                    "reason": f"exception: {str(result)}"
                })
                continue
            
            is_healthy, tools_count = result
            if is_healthy:
                working_servers.append(server)
            else:
                failed_servers.append({
                    "name": server_name,
                    "reason": "mcp_tools_list_failed"
                })
        
        if failed_servers:
            failed_names = [f["name"] for f in failed_servers]
            logger.warning(f"Unavailable MCP servers: {', '.join(failed_names)}")
        
        logger.info(f"Found {len(working_servers)} healthy MCP servers")
        
        self.working_servers = working_servers
        return working_servers
    
    async def test_server_tools(self, server_info: Dict[str, Any]) -> Dict[str, Any]:
        """Test if a single MCP server's tools can be fetched"""
        is_healthy, tools_count = await self.check_server_health_and_get_tools_count(server_info)
        
        if is_healthy:
            return {
                "server": server_info,
                "status": "success",
                "tools_count": tools_count or 0,
                "error": None
            }
        else:
            return {
                "server": server_info,
                "status": "error", 
                "tools_count": 0,
                "error": "MCP tools/list failed"
            }
    
    async def initialize_client(self) -> Tuple[Optional[MultiServerMCPClient], List[Any]]:
        """Initialize MCP client with working servers and fetch tools"""
        
        logger.info("Initializing MCP client")
        
        # First discover working servers
        working_servers = await self.discover_working_servers()
        
        if not working_servers:
            logger.error("No working MCP servers found")
            return None, []
        
        # Test tool fetching for each working server
        logger.info(f"Testing tool fetching for {len(working_servers)} servers")
        
        tool_tests = [
            self.test_server_tools(server) 
            for server in working_servers
        ]
        
        test_results = await asyncio.gather(*tool_tests, return_exceptions=True)
        
        # Filter to servers that can provide tools
        functional_servers = []
        total_tools_expected = 0
        failed_tool_servers = []
        
        for result in test_results:
            if isinstance(result, Exception):
                logger.error(f"Tool test resulted in exception: {result}")
                continue
                
            server_name = result["server"].get("name", "unknown")
            if result["status"] == "success":
                functional_servers.append(result["server"])
                total_tools_expected += result["tools_count"]
            else:
                error_msg = result.get('error', 'unknown error')
                failed_tool_servers.append({
                    "name": server_name,
                    "error": error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
                })
        
        if failed_tool_servers:
            failed_names = [f["name"] for f in failed_tool_servers]
            logger.warning(f"Tool fetch failures: {', '.join(failed_names)}")
        
        if not functional_servers:
            logger.error("No MCP servers can provide tools")
            return None, []
        
        logger.info(f"Found {len(functional_servers)} functional servers with {total_tools_expected} tools")
        
        # Prepare server configuration for MultiServerMCPClient
        server_config = {}
        for server_info in functional_servers:
            server_name = server_info.get("name", "unknown")
            server_config[server_name] = {
                "url": server_info["url"],
                "transport": "streamable_http",
                "description": server_info["description"]
            }
        
        # Create MultiServerMCPClient with functional servers
        try:
            client = MultiServerMCPClient(server_config)
            tools = await client.get_tools()
            
            if not tools:
                logger.warning("No tools were fetched from functional MCP servers")
                return client, []
            
            logger.info(f"Successfully initialized MCP client with {len(tools)} tools")
            
            self.client = client
            self.tools = tools
            return client, tools
            
        except Exception as e:
            logger.error(f"Error creating MCP client or fetching tools: {e}")
            return None, []
    
    async def get_client_and_tools(self) -> Tuple[Optional[MultiServerMCPClient], List[Any]]:
        """Get initialized client and tools, initializing if necessary"""
        if self.client is None or not self.tools:
            return await self.initialize_client()
        return self.client, self.tools
    
    async def cleanup(self):
        """Clean up MCP client connections"""
        if self.client:
            try:
                # Try to close client connections if possible
                # Note: MultiServerMCPClient might not have explicit close method
                # but this allows for graceful cleanup if needed
                if hasattr(self.client, 'close'):
                    await self.client.close()
                
                logger.info("MCP client connections cleaned up")
            except Exception as e:
                logger.error(f"Error during MCP client cleanup: {e}")
            finally:
                self.client = None
                self.tools = []
                self.working_servers = []


# Global instance for reuse
mcp_manager = MCPClientManager() 