"""LLM provider factory."""

from __future__ import annotations

from src.config import LLMConfig
from src.llm.anthropic import AnthropicProvider
from src.llm.base import LLMProvider
from src.llm.openai import OpenAIProvider


def create_llm_provider(config: LLMConfig) -> LLMProvider:
    """Create an LLM provider based on configuration."""
    if config.provider == "anthropic":
        if not config.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        return AnthropicProvider(api_key=config.anthropic_api_key, model=config.anthropic_model)
    elif config.provider == "openai":
        if not config.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set")
        return OpenAIProvider(api_key=config.openai_api_key, model=config.openai_model)
    else:
        raise ValueError(f"Unknown LLM provider: {config.provider}")
