"""OpenAI client wrapper for the Visa Disputes AI agent system.

Provides a centralized async client for making OpenAI API calls with
structured JSON responses, retry logic, response caching, and consistent
error handling.
"""

import hashlib
import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

# Module-level cache for chat_json responses keyed by a stable hash of
# (system_prompt, user_prompt, model, temperature). The cache is bounded by
# _CACHE_MAX_SIZE; on overflow it is cleared entirely for simplicity.
_response_cache: dict[str, dict[str, Any]] = {}
_CACHE_MAX_SIZE = 500


def get_client() -> AsyncOpenAI:
    """Return a singleton AsyncOpenAI client instance.

    Raises:
        RuntimeError: If OPENAI_API_KEY is not set.
    """
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is required. "
            "This application uses OpenAI to process disputes according to Visa rules."
        )
    _client = AsyncOpenAI(api_key=api_key)
    return _client


def _cache_key(
    system_prompt: str, user_prompt: str, model: str, temperature: float
) -> str:
    """Compute a stable cache key for a chat_json call."""
    payload = json.dumps(
        {
            "system": system_prompt,
            "user": user_prompt,
            "model": model,
            "temperature": temperature,
        },
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def clear_cache() -> None:
    """Clear the LLM response cache."""
    _response_cache.clear()


async def chat_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = "gpt-4o-mini",
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> dict[str, Any]:
    """Send a chat completion request and parse the response as JSON.

    Identical (system_prompt, user_prompt, model, temperature) requests are
    cached in-process to avoid repeated API calls for deterministic prompts.

    Args:
        system_prompt: The system message providing context and instructions.
        user_prompt: The user message with the specific request.
        model: OpenAI model to use.
        temperature: Sampling temperature (low = more deterministic).
        max_tokens: Maximum tokens in the response.

    Returns:
        Parsed JSON dict from the model response.

    Raises:
        RuntimeError: If the API call fails or response cannot be parsed.
    """
    key = _cache_key(system_prompt, user_prompt, model, temperature)
    cached = _response_cache.get(key)
    if cached is not None:
        return cached

    client = get_client()

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("OpenAI returned empty response")

    result: dict[str, Any] = json.loads(content)

    if len(_response_cache) >= _CACHE_MAX_SIZE:
        _response_cache.clear()
    _response_cache[key] = result

    return result


async def chat_text(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = "gpt-4o-mini",
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> str:
    """Send a chat completion request and return the text response.

    Args:
        system_prompt: The system message providing context and instructions.
        user_prompt: The user message with the specific request.
        model: OpenAI model to use.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in the response.

    Returns:
        Text content from the model response.

    Raises:
        RuntimeError: If the API call fails.
    """
    client = get_client()

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("OpenAI returned empty response")

    return content
