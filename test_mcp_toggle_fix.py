#!/usr/bin/env python3
"""
Test script to verify MCP server toggle fix works correctly.

This script simulates the MCP server toggle flow to ensure that:
1. Disabling a server removes its tools from the agent
2. Enabling a server adds its tools back to the agent
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

async def test_mcp_toggle_fix():
    """Test that MCP server toggling correctly updates available tools."""
    print("🧪 Testing MCP Server Toggle Fix")
    print("=" * 50)
    
    try:
        from config import settings
        from agent.chat_agent import get_all_tools_with_mcp, clear_chat_agent_cache
        from utils.config_loader import load_mcp_yaml, save_mcp_yaml
        
        # 1. Check initial state
        print("\n1️⃣ Initial State")
        initial_config = load_mcp_yaml()
        enabled_servers = [name for name, config in initial_config.items() if config.get("enabled", True)]
        print(f"   Enabled servers: {enabled_servers}")
        
        initial_tools = await get_all_tools_with_mcp(use_cache=False)
        initial_tool_count = len(initial_tools)
        print(f"   Initial tool count: {initial_tool_count}")
        
        if not enabled_servers:
            print("   ⚠️  No enabled servers found, cannot test toggle")
            return
        
        # Pick first enabled server to toggle
        test_server = enabled_servers[0]
        print(f"   Will test with server: {test_server}")
        
        # 2. Disable the server
        print(f"\n2️⃣ Disabling server: {test_server}")
        config_copy = initial_config.copy()
        config_copy[test_server]["enabled"] = False
        save_mcp_yaml(config_copy)
        print(f"   ✅ Server {test_server} disabled in config")
        
        # 3. Simulate cache clearing (what happens when MCP toggle event is received)
        print("\n3️⃣ Clearing chat agent cache (simulating MCP toggle event)")
        clear_chat_agent_cache()
        print("   ✅ Chat agent cache cleared")
        
        # 4. Get tools after disabling - should have fewer tools
        print("\n4️⃣ Fetching tools after server disable")
        disabled_tools = await get_all_tools_with_mcp(use_cache=False)
        disabled_tool_count = len(disabled_tools)
        print(f"   Tool count after disable: {disabled_tool_count}")
        
        # 5. Re-enable the server
        print(f"\n5️⃣ Re-enabling server: {test_server}")
        config_copy[test_server]["enabled"] = True
        save_mcp_yaml(config_copy)
        print(f"   ✅ Server {test_server} re-enabled in config")
        
        # 6. Clear cache and get tools again
        print("\n6️⃣ Clearing cache and fetching tools after re-enable")
        clear_chat_agent_cache()
        reenabled_tools = await get_all_tools_with_mcp(use_cache=False)
        reenabled_tool_count = len(reenabled_tools)
        print(f"   Tool count after re-enable: {reenabled_tool_count}")
        
        # 7. Restore original config
        print(f"\n7️⃣ Restoring original configuration")
        save_mcp_yaml(initial_config)
        print("   ✅ Original config restored")
        
        # 8. Analyze results
        print(f"\n📊 Results Analysis")
        print(f"   Initial tools:    {initial_tool_count}")
        print(f"   Disabled tools:   {disabled_tool_count}")
        print(f"   Re-enabled tools: {reenabled_tool_count}")
        
        # Check if fix works
        if disabled_tool_count < initial_tool_count:
            print("   ✅ PASS: Disabling server reduced tool count")
        else:
            print("   ❌ FAIL: Disabling server did not reduce tool count")
            
        if reenabled_tool_count == initial_tool_count:
            print("   ✅ PASS: Re-enabling server restored tool count")
        else:
            print("   ❌ FAIL: Re-enabling server did not restore tool count")
            
        if disabled_tool_count < initial_tool_count and reenabled_tool_count == initial_tool_count:
            print("\n🎉 SUCCESS: MCP server toggle fix is working correctly!")
        else:
            print("\n💥 FAILURE: MCP server toggle fix needs more work")
            
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to restore config on error
        try:
            if 'initial_config' in locals():
                save_mcp_yaml(initial_config)
                print("   ✅ Original config restored after error")
        except:
            print("   ❌ Failed to restore config after error")

if __name__ == "__main__":
    asyncio.run(test_mcp_toggle_fix()) 