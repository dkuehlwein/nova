"""
Custom LLM Client for Nova Memory System

Extends graphiti_core's OpenAIClient to handle local LLMs that:
1. Don't support OpenAI's responses.parse() structured output API
2. Return markdown-wrapped JSON responses (```json ... ```)

Uses json_schema response_format for structured outputs, which is more
widely supported by local LLM backends (LM Studio, Ollama, etc.).

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

    It also handles cases where LLMs return lists instead of objects for
    structured outputs (e.g., returning [] instead of {"field": []}).
    """

    def __init__(self, config: LLMConfig | None = None, **kwargs):
        super().__init__(config=config, **kwargs)

    async def _create_structured_completion(
        self,
        model: str,
        messages: list,
        temperature: float | None,
        max_tokens: int,
        response_model: Any,
        reasoning: str | None = None,
        verbosity: str | None = None,
    ):
        """
        Create a structured completion using json_schema response_format.

        Local LLMs don't support OpenAI's responses.parse() structured output API,
        but many (LM Studio, Ollama, vLLM) support json_schema response_format.
        This enforces the schema at the LLM level for correct field names.
        """
        # Build json_schema response format from Pydantic model
        response_format = None
        if response_model is not None and hasattr(response_model, 'model_json_schema'):
            schema = response_model.model_json_schema()
            response_format = {
                'type': 'json_schema',
                'json_schema': {
                    'name': response_model.__name__,
                    'schema': schema,
                    'strict': True
                }
            }

        # Use chat completions with json_schema response format
        request_kwargs = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        if response_format:
            request_kwargs['response_format'] = response_format

        response = await self.client.chat.completions.create(**request_kwargs)

        # Create a simple wrapper that mimics the structure _handle_structured_response expects
        class StructuredResponseWrapper:
            def __init__(self, text: str):
                self.output_text = text

        content = response.choices[0].message.content or '{}'
        return StructuredResponseWrapper(content)

    def _handle_json_response(self, response: Any) -> dict[str, Any]:
        """Handle JSON response parsing with markdown stripping."""
        result = response.choices[0].message.content or '{}'

        # Strip markdown code block wrappers if present
        cleaned_result = strip_markdown_json(result)

        return json.loads(cleaned_result)

    def _handle_structured_response(self, response: Any) -> dict[str, Any]:
        """
        Handle structured response parsing with markdown stripping and schema fixing.

        Local LLMs may return:
        1. Markdown-wrapped JSON (```json ... ```)
        2. Lists instead of objects ([] instead of {"field": []})

        This method handles both cases.
        """
        response_text = response.output_text

        if response_text:
            # Strip markdown code block wrappers if present
            cleaned_text = strip_markdown_json(response_text)
            parsed = json.loads(cleaned_text)

            # Fix schema mismatch: if LLM returns a list but we expect an object,
            # wrap it in the expected structure. This commonly happens with
            # ExtractedEntities where LLMs return [...] instead of {"extracted_entities": [...]}
            if isinstance(parsed, list):
                # Wrap list in expected object structure
                # graphiti expects {"extracted_entities": [...]} for ExtractedEntities
                parsed = {"extracted_entities": parsed}

            return parsed
        elif hasattr(response_text, 'refusal') and response_text.refusal:
            from graphiti_core.llm_client.errors import RefusalError
            raise RefusalError(response_text.refusal)
        else:
            raise Exception(f'Invalid response from LLM: {response_text}')
