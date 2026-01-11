#!/usr/bin/env python3
"""
Generate Virtual Key for Feature Request MCP Server

This script creates a dedicated virtual key for the feature-request service
with appropriate spending limits and model access controls.
"""

import httpx
import json
import sys
import os
from datetime import datetime, timedelta


def generate_virtual_key():
    """Generate a virtual key for the feature-request service."""
    
    # Configuration
    litellm_base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
    master_key = os.getenv("LITELLM_MASTER_KEY", "sk-1234")
    
    # Virtual key configuration (20B+ models only - smaller models are too weak)
    key_config = {
        "models": [
            "gemini-3-flash-preview",  # Latest Gemini model (primary)
        ],
        "metadata": {
            "user": "feature-request-service",
            "description": "Virtual key for feature request MCP server",
            "service": "mcp-feature-request"
        },
        "team_id": "nova-mcp-services",
        "user_id": "feature-request-service",
        "max_budget": 10.0,  # $10 monthly budget
        "budget_duration": "1mo",  # Monthly budget reset
        "tpm_limit": 1000,  # 1000 tokens per minute
        "rpm_limit": 20,    # 20 requests per minute
        "max_parallel_requests": 2,  # Limit concurrent requests
        "aliases": {
            "feature-analyzer": "gemini-3-flash-preview"
        }
    }
    
    headers = {
        "Authorization": f"Bearer {master_key}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"Generating virtual key for feature-request service...")
        print(f"LiteLLM URL: {litellm_base_url}")
        
        response = httpx.post(
            f"{litellm_base_url}/key/generate",
            headers=headers,
            json=key_config,
            timeout=30.0
        )
        
        if response.status_code == 200:
            result = response.json()
            api_key = result.get("key")
            key_name = result.get("key_name", "unknown")
            
            print(f"✅ Virtual key generated successfully!")
            print(f"Key Name: {key_name}")
            print(f"API Key: {api_key}")
            print()
            print("💡 Add this to your environment:")
            print(f"export FEATURE_REQUEST_LITELLM_KEY='{api_key}'")
            print()
            print("🔒 Security features enabled:")
            print(f"- Monthly budget: ${key_config['max_budget']}")
            print(f"- Rate limit: {key_config['rpm_limit']} requests/min")
            print(f"- Token limit: {key_config['tpm_limit']} tokens/min")
            print(f"- Max parallel: {key_config['max_parallel_requests']} requests")
            print(f"- Allowed models: {', '.join(key_config['models'])}")
            
            return api_key
            
        else:
            print(f"❌ Failed to generate virtual key: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except httpx.RequestError as e:
        print(f"❌ Connection error: {e}")
        print("🔧 Make sure LiteLLM is running: docker-compose up -d litellm")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def verify_key(api_key: str):
    """Verify the generated key works correctly."""
    
    litellm_base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"\n🧪 Testing virtual key...")
        
        # Test key info endpoint
        response = httpx.get(
            f"{litellm_base_url}/key/info",
            headers=headers,
            timeout=10.0
        )
        
        if response.status_code == 200:
            key_info = response.json()
            print(f"✅ Key verification successful!")
            print(f"Key valid until: {key_info.get('expires', 'Never')}")
            print(f"Remaining budget: ${key_info.get('max_budget', 'Unknown')}")
            return True
        else:
            print(f"❌ Key verification failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Key verification error: {e}")
        return False


if __name__ == "__main__":
    print("🔑 LiteLLM Virtual Key Generator for Feature Request Service")
    print("=" * 60)
    
    # Check if LiteLLM is running
    litellm_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
    try:
        health_response = httpx.get(f"{litellm_url}/health/readiness", timeout=5.0)
        if health_response.status_code != 200:
            print(f"❌ LiteLLM not ready. Start it with: docker-compose up -d litellm")
            sys.exit(1)
    except:
        print(f"❌ Cannot connect to LiteLLM at {litellm_url}")
        print("🔧 Make sure LiteLLM is running: docker-compose up -d litellm")
        sys.exit(1)
    
    # Generate the key
    api_key = generate_virtual_key()
    
    if api_key:
        # Verify the key works
        verify_key(api_key)
        print(f"\n🎉 Virtual key setup complete!")
    else:
        print(f"\n❌ Virtual key generation failed!")
        sys.exit(1)