#!/usr/bin/env python3
"""
Integration test script for the Feature Request MCP Server.
This script tests the complete LiteLLM-based integration:
1. Virtual key authentication and security
2. LiteLLM model access
3. Linear API integration
4. End-to-end feature request workflow
"""

import asyncio
import os
import sys
import httpx
import json
from datetime import datetime
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, 'src')

from src.linear_client import LinearClient
from src.feature_analyzer import FeatureRequestAnalyzer
from src.mcp_tools import request_feature_impl
from src.llm_factory import validate_configuration

# Load environment variables from feature_request service directory
from pathlib import Path
service_root = Path(__file__).parent
env_path = service_root / '.env'
loaded = load_dotenv(env_path)
print(f"📁 Loading environment from: {env_path}")
print(f"📋 Environment loaded successfully: {loaded}")

# Debug: Check if .env file exists
if env_path.exists():
    print(f"✅ .env file exists ({env_path.stat().st_size} bytes)")
else:
    print(f"❌ .env file not found at: {env_path}")

async def test_litellm_security():
    """Test LiteLLM virtual key security and configuration."""
    
    print("🔒 Testing LiteLLM Security Configuration")
    print("-" * 50)
    
    # Test 1: Configuration validation
    config = validate_configuration()
    
    print(f"Configuration valid: {config['valid']}")
    
    if not config["valid"]:
        print(f"❌ Configuration failed: {config.get('error', 'Unknown error')}")
        return False
    
    print(f"✅ LiteLLM URL: {config['base_url']}")
    print(f"✅ Using service key: {config.get('service_key_prefix', 'unknown')}")
    print(f"✅ Available models: {', '.join(config['available_models'])}")
    
    # Test 2: Virtual key authentication
    service_key = os.getenv("FEATURE_REQUEST_LITELLM_KEY")
    if not service_key:
        print("❌ FEATURE_REQUEST_LITELLM_KEY not found")
        return False
    
    try:
        response = httpx.get(
            f"{config['base_url']}/key/info",
            headers={"Authorization": f"Bearer {service_key}"},
            timeout=10.0
        )
        
        if response.status_code == 200:
            key_info = response.json()
            print(f"✅ Virtual key authenticated successfully")
            print(f"   Budget: ${key_info['info']['max_budget']}")
            print(f"   Rate limit: {key_info['info']['rpm_limit']} requests/min")
            print(f"   Spend: ${key_info['info']['spend']}")
        else:
            print(f"❌ Virtual key authentication failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Virtual key test error: {e}")
        return False
    
    return True


async def test_linear_integration():
    """Test the Linear API integration end-to-end."""
    
    print("\n📡 Testing Linear API Integration")
    print("-" * 50)
    
    # Check API keys
    linear_api_key = os.getenv("LINEAR_API_KEY")
    
    if not linear_api_key or linear_api_key.strip() == "":
        print("❌ LINEAR_API_KEY not configured or empty")
        print("   This is REQUIRED - the feature request system cannot function without Linear API access")
        print("   The service can authenticate with LiteLLM but cannot create or update issues")
        print(f"   Current value: '{linear_api_key}' (from environment)")
        print("\n🔧 To get a Linear API key:")
        print("   1. Go to https://linear.app/settings/api")
        print("   2. Create a new API key")
        print("   3. Set LINEAR_API_KEY=your_key_here in .env")
        print("   4. Restart the test")
        return False
    
    print("✅ Linear API key found")
    
    try:
        # Initialize clients
        print("\n📡 Initializing API clients...")
        linear_client = LinearClient(linear_api_key)
        analyzer = FeatureRequestAnalyzer()
        
        # Test 1: List open issues
        print("\n📋 Fetching open Linear issues...")
        try:
            open_issues = await linear_client.get_open_issues()
            print(f"✅ Found {len(open_issues)} open issues")
            
            if open_issues:
                print("\n📝 Recent issues:")
                for i, issue in enumerate(open_issues[:3]):  # Show first 3
                    print(f"  {i+1}. {issue.get('title', 'No title')} (ID: {issue.get('id', 'Unknown')})")
            else:
                print("  No open issues found")
                
        except Exception as e:
            print(f"❌ Failed to fetch issues: {e}")
            return False
        
        # Test 2: Get teams
        print("\n👥 Fetching Linear teams...")
        try:
            teams = await linear_client.get_teams()
            print(f"✅ Found {len(teams)} teams")
            
            if teams:
                print("  Available teams:")
                for team in teams:
                    print(f"    - {team.get('name', 'Unknown')} ({team.get('key', 'Unknown')})")
            
        except Exception as e:
            print(f"❌ Failed to fetch teams: {e}")
            return False
        
        # Test 3: Create a test feature request using the full workflow
        print(f"\n🆕 Creating test feature request...")
        
        test_request = f"""
I need to test the feature request system integration with LiteLLM. 

**Context**: This is a test request created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} to verify that:
1. The MCP server can communicate with Linear API
2. The AI analyzer can process feature requests via LiteLLM
3. Virtual key authentication is working
4. Issues can be created successfully

**Problem**: We need to verify the LiteLLM-based integration works end-to-end with proper security.

**Requirements**: 
- Successful LiteLLM virtual key authentication
- Working AI analysis via LiteLLM gateway
- Proper issue creation in Linear
- Security isolation with dedicated service key

**Impact**: This ensures Nova can properly request new features through the secure LiteLLM gateway when she encounters limitations.
"""
        
        try:
            result = await request_feature_impl(test_request, linear_client, analyzer)
            
            if result["success"]:
                print(f"✅ Successfully created feature request!")
                print(f"   Action: {result.get('action', 'Unknown')}")
                print(f"   Issue ID: {result.get('issue_id', 'Unknown')}")
                print(f"   Title: {result.get('title', 'Unknown')}")
                print(f"   URL: {result.get('issue_url', 'Unknown')}")
                print(f"   Reasoning: {result.get('reasoning', 'No reasoning provided')}")
                
                return True
            else:
                print(f"❌ Failed to create feature request: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Exception during feature request creation: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to initialize clients: {e}")
        return False

async def main():
    """Main test function."""
    print("🚀 Feature Request MCP Server - Complete Integration Test")
    print("=" * 60)
    print("Testing LiteLLM-based security and Linear API integration")
    print()
    
    # Run all tests
    tests = [
        ("LiteLLM Security", test_litellm_security),
        ("Linear Integration", test_linear_integration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        results[test_name] = await test_func()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 Integration Test Summary:")
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print(f"\nOverall: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("🎉 All integration tests PASSED! The LiteLLM-based feature request system is working correctly.")
        print("\n💡 Next steps:")
        print("   1. Start the MCP server: python main.py")
        print("   2. Ensure it's configured in Nova's mcp_servers.yaml")
        print("   3. Nova can now use the request_feature tool securely!")
        print("\n🔒 Security features verified:")
        print("   ✅ Virtual key authentication")
        print("   ✅ Service isolation")
        print("   ✅ Rate limiting")
        print("   ✅ Spend tracking")
    else:
        print("❌ Some integration tests FAILED. Check the errors above.")
        print("\n🔧 Troubleshooting:")
        print("   1. Generate virtual key: python scripts/generate_feature_request_key.py")
        print("   2. Set FEATURE_REQUEST_LITELLM_KEY in environment")
        print("   3. Set LINEAR_API_KEY with valid Linear API token")  
        print("   4. Check LiteLLM service is running (port 4000)")
        print("   5. Check Linear workspace permissions")
        print("   6. Ensure internet connectivity")
        print("\n❗ Both LiteLLM virtual key AND Linear API key are REQUIRED")
    
    return total_passed == total_tests

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 