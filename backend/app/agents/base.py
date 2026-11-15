"""Base agent class and simple test implementations."""

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for all delivery agents.

    Provides common functionality for LLM interaction and message handling.
    Subclasses implement specific agent behaviors.

    Attributes:
        llm_provider: The LLM provider for generating completions.
    """

    def __init__(self, llm_provider: LLMProvider):
        """
        Initialize the agent with an LLM provider.

        Args:
            llm_provider: Configured LLM provider instance.
        """
        self.llm_provider = llm_provider

    @property
    def system_prompt(self) -> str:
        """
        System prompt for the agent.

        Override in subclasses to provide agent-specific instructions.
        """
        return "You are a helpful delivery agent assistant."

    async def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Process an agent request.

        Override in subclasses to implement specific agent logic.

        Args:
            payload: Request payload containing task-specific data.

        Returns:
            Processing result as a dictionary.

        Raises:
            NotImplementedError: Base class doesn't implement processing.
        """
        raise NotImplementedError("Subclasses must implement process()")

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        response_model: type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> str | BaseModel:
        """
        Call the LLM with logging and error handling.

        Wrapper around llm_provider.complete() with added logging
        and standardized error handling.

        Args:
            messages: List of message dictionaries.
            response_model: Optional Pydantic model for structured output.
            **kwargs: Additional parameters for the LLM.

        Returns:
            LLM response (string or parsed model).
        """
        # Prepend system prompt if not already present
        if messages and messages[0].get("role") != "system":
            messages = [{"role": "system", "content": self.system_prompt}] + messages

        logger.debug(
            f"Agent {self.__class__.__name__} calling LLM with {len(messages)} messages"
        )

        if response_model is not None:
            result = await self.llm_provider.complete_structured(
                messages=messages,
                response_model=response_model,
                **kwargs,
            )
        else:
            result = await self.llm_provider.complete(
                messages=messages,
                **kwargs,
            )

        logger.debug(f"Agent {self.__class__.__name__} received LLM response")
        return result


class EchoAgent(BaseAgent):
    """
    Simple test agent that echoes back the payload.

    Used for testing the full async pipeline without requiring real LLM keys.
    Returns a mock response with timestamp and echoed payload.
    """

    @property
    def system_prompt(self) -> str:
        """System prompt for echo agent."""
        return "You are an echo agent for testing purposes."

    async def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Echo back the payload with metadata.

        Args:
            payload: Request payload to echo.

        Returns:
            Response containing echoed payload and metadata.
        """
        logger.info(f"EchoAgent processing payload: {payload}")

        return {
            "type": "echo_response",
            "echoed_payload": payload,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "agent": self.__class__.__name__,
            "reasoning": "Echoed payload for testing pipeline",
            "confidence": "high",
            "llm_available": self.llm_provider.is_available,
        }
