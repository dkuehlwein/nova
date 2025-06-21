#!/usr/bin/env python3
"""
Integration test script for the Feature Request MCP Server.
This script tests the actual Linear API integration by:
1. Listing open issues
2. Creating a new test feature request
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, 'src')

from src.linear_client import LinearClient
from src.feature_analyzer import FeatureRequestAnalyzer
from src.mcp_tools import request_feature_impl

# Load environment variables
load_dotenv()

async def test_linear_integration():
    """Test the Linear API integration end-to-end."""
    
    print("🚀 Feature Request MCP Server Integration Test")
    print("=" * 50)
    
    # Check API keys
    linear_api_key = os.getenv("LINEAR_API_KEY")
    google_api_key = os.getenv("GOOGLE_API_KEY")
    
    if not linear_api_key:
        print("❌ LINEAR_API_KEY not found in environment variables")
        return False
    
    if not google_api_key:
        print("❌ GOOGLE_API_KEY not found in environment variables")
        return False
    
    print("✅ API keys found")
    
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
I need to test the feature request system integration. 

**Context**: This is a test request created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} to verify that:
1. The MCP server can communicate with Linear API
2. The AI analyzer can process feature requests
3. Issues can be created successfully

**Problem**: We need to verify the integration works end-to-end before deploying to production.

**Requirements**: 
- Successful Linear API communication
- Working AI analysis
- Proper issue creation

**Impact**: This ensures Nova can properly request new features when she encounters limitations.
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
    print("Starting Feature Request MCP Server integration test...\n")
    
    success = await test_linear_integration()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Integration test PASSED! The feature request system is working correctly.")
        print("\n💡 Next steps:")
        print("   1. Start the MCP server: python main.py")
        print("   2. Ensure it's configured in Nova's mcp_servers.yaml")
        print("   3. Nova can now use the request_feature tool!")
    else:
        print("❌ Integration test FAILED. Check the errors above.")
        print("\n🔧 Troubleshooting:")
        print("   1. Verify LINEAR_API_KEY is valid")
        print("   2. Verify GOOGLE_API_KEY is valid")  
        print("   3. Check Linear workspace permissions")
        print("   4. Ensure internet connectivity")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 