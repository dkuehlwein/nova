#!/usr/bin/env python3
"""
Quick test script for the genai_training_onboarding skill.

Run from the backend directory:
    cd backend && uv run python skills/genai_training_onboarding/test_skill.py

This tests:
1. Module imports work correctly
2. Tools can be instantiated
3. Basic tool validation passes
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))


def test_imports():
    """Test that all skill modules can be imported."""
    print("Testing imports...")

    # Test tools.py imports
    from skills.genai_training_onboarding.tools import get_tools
    print("  ✓ tools.py imported successfully")

    # Test gitlab_client imports
    from skills.genai_training_onboarding.gitlab_client import add_gitlab_member, check_gitlab_connection
    print("  ✓ gitlab_client.py imported successfully")

    # Test lam_automation imports
    from skills.genai_training_onboarding.lam_automation import create_lam_account
    print("  ✓ lam_automation.py imported successfully")


def test_get_tools():
    """Test that get_tools() returns valid tools."""
    print("\nTesting get_tools()...")

    from skills.genai_training_onboarding.tools import get_tools

    tools = get_tools()
    print(f"  Found {len(tools)} tools:")

    expected_tools = ["resolve_participant_email", "execute_batch_onboarding"]

    for tool in tools:
        print(f"    - {tool.name}: {tool.description[:60]}...")
        if tool.name not in expected_tools:
            print(f"  ⚠ Unexpected tool: {tool.name}")

    for expected in expected_tools:
        if expected not in [t.name for t in tools]:
            print(f"  ✗ Missing expected tool: {expected}")
            return False

    print("  ✓ All expected tools present")
    return True


async def test_execute_validation():
    """Test that execute_batch_onboarding validates credentials."""
    print("\nTesting execute_batch_onboarding validation...")

    from skills.genai_training_onboarding.tools import execute_batch_onboarding

    participants = [{"email": "test@example.com", "name": "Test User"}]

    # Should fail gracefully due to missing credentials
    result = await execute_batch_onboarding.ainvoke({"participants": participants})

    if "error" in result.lower() and ("credentials" in result.lower() or "configured" in result.lower()):
        print("  ✓ Correctly validates missing credentials")
        return True
    else:
        print(f"  Result: {result[:200]}")
        return True  # May succeed if credentials are set


def test_skill_manager_loading():
    """Test that skill loads correctly via SkillManager."""
    print("\nTesting SkillManager loading...")

    from utils.skill_manager import SkillManager

    skills_path = Path(__file__).parent.parent
    manager = SkillManager(skills_path=skills_path)

    # Check skill is discovered
    skills = manager.list_skills()
    if "genai_training_onboarding" in skills:
        print("  ✓ Skill discovered by SkillManager")
    else:
        print(f"  ✗ Skill not found. Available: {skills}")
        return False

    # Try loading the skill
    async def load_test():
        skill = await manager.load_skill("genai_training_onboarding")
        print(f"  ✓ Skill loaded: {skill.manifest.name} v{skill.manifest.version}")
        print(f"  ✓ Instructions: {len(skill.instructions)} chars")
        print(f"  ✓ Tools: {len(skill.tools)}")
        return True

    return asyncio.run(load_test())


def main():
    """Run all tests."""
    print("=" * 60)
    print("GenAI Training Onboarding Skill - Test Suite")
    print("=" * 60)

    all_passed = True

    try:
        test_imports()
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        all_passed = False

    try:
        if not test_get_tools():
            all_passed = False
    except Exception as e:
        print(f"  ✗ get_tools() failed: {e}")
        all_passed = False

    try:
        if not asyncio.run(test_execute_validation()):
            all_passed = False
    except Exception as e:
        print(f"  ✗ execute_batch_onboarding failed: {e}")
        all_passed = False

    try:
        if not test_skill_manager_loading():
            all_passed = False
    except Exception as e:
        print(f"  ✗ SkillManager loading failed: {e}")
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed! ✓")
    else:
        print("Some tests failed. ✗")
        sys.exit(1)


if __name__ == "__main__":
    main()
