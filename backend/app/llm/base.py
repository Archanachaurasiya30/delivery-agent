"""Abstract LLM provider interface."""

from abc import ABC, abstractmethod
from typing import Any, TypeVar, Union

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    def __init__(self, message: str, provider: str | None = None, model: str | None = None):
        self.message = message
        self.provider = provider
        self.model = model
        super().__init__(message)


class LLMConnectionError(LLMError):
    """Raised when connection to LLM provider fails."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded."""

    pass


class LLMAuthenticationError(LLMError):
    """Raised when authentication fails."""

    pass


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Defines the interface for all LLM providers to implement,
    enabling consistent usage across different backends (OpenAI, Anthropic, Azure, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model to use for completions."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is properly configured and available."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        response_format: type[T] | None = None,
        **kwargs: Any,
    ) -> Union[str, T]:
        """
        Generate a completion from the LLM.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys.
            model: Optional model override. Uses default_model if not specified.
            response_format: Optional Pydantic model for structured output parsing.
            **kwargs: Additional provider-specific parameters.

        Returns:
            String response if no response_format, otherwise parsed Pydantic model.

        Raises:
            LLMError: On provider-specific errors.
            LLMConnectionError: On connection failures.
            LLMRateLimitError: On rate limit exceeded.
            LLMAuthenticationError: On auth failures.
        """
        ...

    async def complete_structured(
        self,
        messages: list[dict[str, Any]],
        response_model: type[T],
        model: str | None = None,
        **kwargs: Any,
    ) -> T:
        """
        Convenience method for structured output with a Pydantic model.

        This is a wrapper around complete() that ensures response_format is used.

        Args:
            messages: List of message dictionaries.
            response_model: Pydantic model class for response parsing.
            model: Optional model override.
            **kwargs: Additional parameters.

        Returns:
            Parsed Pydantic model instance.
        """
        result = await self.complete(
            messages=messages,
            model=model,
            response_format=response_model,
            **kwargs,
        )
        # Type guard - result should be the model type when response_format is provided
        if isinstance(result, response_model):
            return result
        raise LLMError(
            f"Expected {response_model.__name__}, got {type(result).__name__}",
            provider=self.name,
        )
