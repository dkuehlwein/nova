"""
Example skill tools for testing the skills system.

These tools demonstrate how skill-specific tools are defined and loaded dynamically.
"""

from langchain_core.tools import tool


@tool
def say_hello(name: str) -> str:
    """
    Generate a friendly greeting for a given name.

    Args:
        name: The name of the person to greet

    Returns:
        A friendly greeting message
    """
    return f"Hello, {name}! Welcome to Nova's skills system."


@tool
def say_goodbye(name: str) -> str:
    """
    Generate a farewell message for a given name.

    Args:
        name: The name of the person to bid farewell to

    Returns:
        A farewell message
    """
    return f"Goodbye, {name}! Thanks for testing Nova's skills system."


def get_tools():
    """Return all tools provided by this skill."""
    return [say_hello, say_goodbye]
