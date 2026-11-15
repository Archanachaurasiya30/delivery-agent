"""LLM provider abstraction layer.

This module provides a unified interface for interacting with various LLM providers
(OpenAI, Anthropic, Azure OpenAI) through LiteLLM.

Usage:
    from app.llm import get_llm_provider, LLMProvider

    # As FastAPI dependency
    @router.get("/endpoint")
    async def endpoint(provider: LLMProvider = Depends(get_llm_provider)):
        response = await provider.complete([{"role": "user", "content": "Hello"}])

    # Direct usage
    from app.llm import llm_provider
    response = await llm_provider.complete([{"role": "user", "content": "Hello"}])
"""

from app.llm.base import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
)
from app.llm.factory import create_llm_provider, get_llm_provider, llm_provider
from app.llm.litellm_provider import LiteLLMProvider

__all__ = [
    # Base classes and exceptions
    "LLMProvider",
    "LLMError",
    "LLMConnectionError",
    "LLMRateLimitError",
    "LLMAuthenticationError",
    # Implementations
    "LiteLLMProvider",
    # Factory
    "create_llm_provider",
    "get_llm_provider",
    "llm_provider",
]
