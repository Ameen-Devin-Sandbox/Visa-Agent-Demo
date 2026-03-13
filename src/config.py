"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


@dataclass(frozen=True)
class LLMConfig:
    provider: str = os.getenv("LLM_PROVIDER", "anthropic")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    max_tokens: int = 4096
    temperature: float = 0.1


@dataclass(frozen=True)
class QueueConfig:
    max_concurrent_tasks: int = int(os.getenv("MAX_CONCURRENT_TASKS", "5"))
    poll_interval_seconds: float = 1.0


@dataclass(frozen=True)
class AgentConfig:
    max_retries: int = 3
    retry_delay_seconds: float = 2.0


@dataclass(frozen=True)
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    queue: QueueConfig = field(default_factory=QueueConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    knowledge_path: Path = PROJECT_ROOT / "knowledge"
