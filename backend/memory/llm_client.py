"""
Custom LLM Client for Nova Memory System

Extends graphiti_core's OpenAIClient to handle local LLMs that return
markdown-wrapped JSON responses (```json ... ```).

NOTE: This is a workaround for a known issue with graphiti-core and local LLMs.
See: https://github.com/getzep/graphiti/issues/1120
This fix may become unnecessary in a future graphiti-core release.
"""

import json
import re
from typing import Any

from graphiti_core.llm_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig


def strip_markdown_json(text: str) -> str:
    """
    Strip markdown code block wrappers from JSON responses.

    Local LLMs often return JSON wrapped in markdown code blocks like:
    ```json
    {"key": "value"}
    ```

    This function extracts the raw JSON content.
    """
    if not text:
        return text

    # Pattern to match ```json ... ``` or ``` ... ```
    # Handles optional language specifier and whitespace
    pattern = r'^```(?:json)?\s*\n?(.*?)\n?```\s*$'
    match = re.match(pattern, text.strip(), re.DOTALL | re.IGNORECASE)

    if match:
        return match.group(1).strip()

    return text


class MarkdownStrippingOpenAIClient(OpenAIClient):
    """
    OpenAI-compatible client that handles markdown-wrapped JSON responses.

    Local LLMs (via LiteLLM) may not fully support the json_object response
    format and instead return JSON wrapped in markdown code blocks. This
    client strips those wrappers before parsing.
    """

    def __init__(self, config: LLMConfig | None = None, **kwargs):
        super().__init__(config=config, **kwargs)

    def _handle_json_response(self, response: Any) -> dict[str, Any]:
        """Handle JSON response parsing with markdown stripping."""
        result = response.choices[0].message.content or '{}'

        # Strip markdown code block wrappers if present
        cleaned_result = strip_markdown_json(result)

        return json.loads(cleaned_result)

    def _handle_structured_response(self, response: Any) -> dict[str, Any]:
        """Handle structured response parsing with markdown stripping."""
        response_text = response.output_text

        if response_text:
            # Strip markdown code block wrappers if present
            cleaned_text = strip_markdown_json(response_text)
            return json.loads(cleaned_text)
        elif hasattr(response_text, 'refusal') and response_text.refusal:
            from graphiti_core.llm_client.errors import RefusalError
            raise RefusalError(response_text.refusal)
        else:
            raise Exception(f'Invalid response from LLM: {response_text}')
