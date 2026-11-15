"""LLM provider factory for config-based provider creation."""

from functools import lru_cache

from app.config import Settings, settings
from app.llm.base import LLMProvider
from app.llm.litellm_provider import LiteLLMProvider


def create_llm_provider(provider_settings: Settings) -> LLMProvider:
    """
    Create an LLM provider based on configuration.

    Args:
        provider_settings: Application settings with provider configuration.

    Returns:
        Configured LLM provider instance.

    Raises:
        ValueError: If the configured provider is unknown.
    """
    provider_name = provider_settings.llm_provider.lower()

    if provider_name == "litellm":
        return LiteLLMProvider(provider_settings)

    raise ValueError(
        f"Unknown LLM provider: {provider_name}. "
        f"Supported providers: litellm"
    )


@lru_cache(maxsize=1)
def _get_singleton_provider() -> LLMProvider:
    """Get or create the singleton LLM provider instance."""
    return create_llm_provider(settings)


# Module-level singleton for convenience
llm_provider = _get_singleton_provider()


def get_llm_provider() -> LLMProvider:
    """
    FastAPI dependency for getting the LLM provider.

    Usage:
        @router.get("/endpoint")
        async def endpoint(provider: LLMProvider = Depends(get_llm_provider)):
            ...

    Returns:
        The configured LLM provider instance.
    """
    return llm_provider
