"""Agent implementations for delivery intelligence.

This module provides Deep Agent-based implementations for delivery tasks
including sprint planning, standup facilitation, blocker resolution, and release management.
"""

from app.agents.base import BaseAgent, EchoAgent
from app.agents.deep_agent import (
    create_delivery_agent,
    invoke_delivery_agent,
    DELIVERY_TOOLS,
    SYSTEM_PROMPTS,
)
from app.agents.tools import DatabaseTools, create_tool_functions

__all__ = [
    # Legacy (for backwards compatibility)
    "BaseAgent",
    "EchoAgent",
    # Deep Agents (primary)
    "create_delivery_agent",
    "invoke_delivery_agent",
    "DELIVERY_TOOLS",
    "SYSTEM_PROMPTS",
    # Database-connected tools
    "DatabaseTools",
    "create_tool_functions",
]
