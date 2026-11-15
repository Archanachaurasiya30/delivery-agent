"""Deep Agent implementation using LangChain Deep Agents SDK.

This module provides the delivery agent built on top of deepagents library,
with built-in task planning, context management, and memory capabilities.
"""

import logging
import os
from typing import Any

from deepagents import create_deep_agent

from app.config import settings

logger = logging.getLogger(__name__)


def _configure_llm_env() -> None:
    """
    Configure environment variables for LLM providers.

    Deep Agents uses environment variables for API keys.
    This ensures our settings are propagated to the agent.
    """
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.azure_api_key:
        os.environ["AZURE_API_KEY"] = settings.azure_api_key
    if settings.azure_api_base:
        os.environ["AZURE_API_BASE"] = settings.azure_api_base


# Delivery-specific tools for the agent
def get_team_capacity(sprint_id: str | None = None) -> dict[str, Any]:
    """
    Get team capacity for sprint planning.

    Args:
        sprint_id: Optional sprint ID. If not provided, returns current sprint capacity.

    Returns:
        Dictionary with team member availability and capacity hours.
    """
    # Mock implementation - will be connected to real data in Phase 2
    return {
        "sprint_id": sprint_id or "current",
        "total_capacity_hours": 160,
        "team_members": [
            {"name": "Dev 1", "available_hours": 32, "skills": ["backend", "python"]},
            {"name": "Dev 2", "available_hours": 40, "skills": ["frontend", "react"]},
            {"name": "Dev 3", "available_hours": 32, "skills": ["fullstack"]},
            {"name": "Dev 4", "available_hours": 24, "skills": ["backend", "devops"]},
            {"name": "Dev 5", "available_hours": 32, "skills": ["frontend", "testing"]},
        ],
    }


def get_backlog_items(priority: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """
    Get backlog items for sprint planning.

    Args:
        priority: Filter by priority (high, medium, low). None returns all.
        limit: Maximum number of items to return.

    Returns:
        List of backlog items with estimates and dependencies.
    """
    # Mock implementation - will be connected to real data in Phase 2
    items = [
        {"id": "TASK-101", "title": "User authentication flow", "priority": "high", "estimate_hours": 16, "skills": ["backend", "frontend"]},
        {"id": "TASK-102", "title": "Dashboard charts", "priority": "high", "estimate_hours": 12, "skills": ["frontend", "react"]},
        {"id": "TASK-103", "title": "API rate limiting", "priority": "medium", "estimate_hours": 8, "skills": ["backend"]},
        {"id": "TASK-104", "title": "Unit test coverage", "priority": "medium", "estimate_hours": 16, "skills": ["testing"]},
        {"id": "TASK-105", "title": "Documentation update", "priority": "low", "estimate_hours": 4, "skills": ["docs"]},
    ]

    if priority:
        items = [i for i in items if i["priority"] == priority]

    return items[:limit]


def get_sprint_status(sprint_id: str | None = None) -> dict[str, Any]:
    """
    Get current sprint status with task breakdown.

    Args:
        sprint_id: Sprint ID. None returns current sprint.

    Returns:
        Sprint status with task counts and blockers.
    """
    # Mock implementation
    return {
        "sprint_id": sprint_id or "SPRINT-23",
        "name": "Sprint 23",
        "start_date": "2026-02-03",
        "end_date": "2026-02-14",
        "status": "in_progress",
        "tasks": {
            "total": 12,
            "done": 5,
            "in_progress": 4,
            "todo": 2,
            "blocked": 1,
        },
        "blockers": [
            {"task_id": "TASK-098", "description": "Waiting for API access", "blocked_since": "2026-02-06"},
        ],
    }


def get_developer_status(developer_id: str | None = None) -> list[dict[str, Any]]:
    """
    Get developer status for standup.

    Args:
        developer_id: Specific developer ID. None returns all developers.

    Returns:
        List of developer statuses with current tasks.
    """
    # Mock implementation
    developers = [
        {
            "id": "dev-1",
            "name": "Dev 1",
            "current_task": "TASK-097",
            "status": "on_track",
            "blockers": [],
        },
        {
            "id": "dev-2",
            "name": "Dev 2",
            "current_task": "TASK-098",
            "status": "blocked",
            "blockers": ["Waiting for API access from external team"],
        },
    ]

    if developer_id:
        return [d for d in developers if d["id"] == developer_id]
    return developers


# All tools available to the delivery agent
DELIVERY_TOOLS = [
    get_team_capacity,
    get_backlog_items,
    get_sprint_status,
    get_developer_status,
]

# System prompts for different agent types
SYSTEM_PROMPTS = {
    "delivery": """You are an AI-powered Delivery Manager assistant. Your role is to help teams with:

1. **Sprint Planning**: Analyze backlog items and team capacity to propose sprint compositions.
   - Consider task priorities, estimates, and team skills
   - Respect capacity constraints
   - Identify dependencies and blockers

2. **Daily Standups**: Collect and summarize team status updates.
   - Ask about progress, blockers, and plans
   - Identify patterns and concerns
   - Generate concise summaries

3. **Blocker Resolution**: Detect and help resolve blockers.
   - Identify who can help unblock
   - Suggest escalation when needed
   - Track resolution progress

4. **Release Management**: Assess release readiness.
   - Check task completion
   - Identify remaining blockers
   - Generate changelogs

Always explain your reasoning clearly. When proposing actions, provide confidence levels and alternatives.
You propose, humans approve - never take autonomous actions on production systems.""",

    "sprint_planning": """You are a Sprint Planning assistant. Your goal is to propose optimal sprint compositions.

Given the team capacity and backlog items:
1. Analyze available capacity (hours, skills)
2. Review backlog priorities and estimates
3. Match tasks to team members based on skills
4. Respect capacity limits (don't overcommit)
5. Consider task dependencies

Provide a clear sprint proposal with:
- Which tasks to include and why
- Task assignments by team member
- Capacity utilization breakdown
- Risks or concerns
- Confidence level in the proposal

Format your proposal as a structured JSON-like response that can be parsed.""",

    "standup": """You are a Standup Facilitator. Help the team run efficient daily standups.

For each team member, gather:
1. What they completed yesterday
2. What they're working on today
3. Any blockers or concerns

Then synthesize:
- Team-wide progress summary
- Active blockers requiring attention
- Cross-team dependencies
- Action items

Be concise and actionable. Highlight any concerning patterns.""",

    "blocker_detection": """You are a Blocker Detection specialist. Your goal is to identify and help resolve blocked work.

Analyze the current sprint and team status to:
1. Identify tasks that have been in progress for too long
2. Detect patterns that suggest hidden blockers
3. Suggest specific team members who could help unblock
4. Recommend escalation when necessary

For each blocker, provide:
- The blocked task and how long it's been stuck
- Likely cause of the blocker
- Suggested resolver (team member best suited to help)
- Recommended action (pair programming, escalate, split task, etc.)
- Urgency level (low, medium, high, critical)

Be proactive and specific in your recommendations.""",

    "release_management": """You are a Release Manager assistant. Your goal is to assess release readiness and generate release artifacts.

When assessing readiness:
1. Check task completion rate
2. Identify any open blockers
3. Review testing status
4. Assess risks

When generating changelog:
1. Group completed tasks by category (feature, bugfix, improvement)
2. Write user-friendly descriptions
3. Highlight breaking changes
4. Include contributor acknowledgments

Provide:
- Go/No-Go recommendation with reasoning
- Risk assessment
- Changelog content
- Stakeholder summary (non-technical)

Be clear about any concerns that should delay a release.""",

    "echo": """You are a test agent that echoes back requests for testing purposes.
Simply acknowledge the input and return it with some processing metadata.""",
}


def create_delivery_agent(
    agent_type: str = "delivery",
    model: str | None = None,
) -> Any:
    """
    Create a Deep Agent configured for delivery management.

    Args:
        agent_type: Type of agent to create. Options:
            - "delivery": General delivery manager
            - "sprint_planning": Specialized for sprint planning
            - "standup": Specialized for standups
            - "echo": Test agent
        model: LLM model to use (litellm format). Defaults to settings.deep_agent_model.

    Returns:
        Configured Deep Agent instance.
    """
    _configure_llm_env()

    system_prompt = SYSTEM_PROMPTS.get(agent_type, SYSTEM_PROMPTS["delivery"])
    target_model = model or settings.deep_agent_model

    logger.info(f"Creating Deep Agent: type={agent_type}, model={target_model}")

    agent = create_deep_agent(
        tools=DELIVERY_TOOLS,
        system_prompt=system_prompt,
        model=target_model,
    )

    return agent


async def invoke_delivery_agent(
    agent_type: str,
    message: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Invoke a delivery agent with a message.

    This is the main entry point for agent processing.

    Args:
        agent_type: Type of agent to use (delivery, sprint_planning, standup, echo).
        message: User message/request to process.
        context: Optional context data to include.

    Returns:
        Agent response with content, reasoning, and metadata.
    """
    agent = create_delivery_agent(agent_type)

    # Build messages with context
    messages = []
    if context:
        context_msg = f"Context data:\n```json\n{context}\n```\n\n"
        messages.append({"role": "user", "content": context_msg + message})
    else:
        messages.append({"role": "user", "content": message})

    logger.info(f"Invoking agent: type={agent_type}, message_length={len(message)}")

    try:
        # Deep Agents use invoke() - it handles the full agent loop internally
        result = agent.invoke({"messages": messages})

        # Extract the final response
        response_messages = result.get("messages", [])
        final_message = response_messages[-1] if response_messages else None

        if final_message:
            content = final_message.content if hasattr(final_message, "content") else str(final_message)
        else:
            content = "No response generated"

        logger.info(f"Agent completed: type={agent_type}, response_length={len(content)}")

        return {
            "type": f"{agent_type}_response",
            "content": content,
            "reasoning": "Processed by Deep Agent with task planning and tool use",
            "confidence": "high",
            "agent": f"DeepAgent[{agent_type}]",
            "tool_calls": _extract_tool_calls(response_messages),
        }

    except Exception as e:
        logger.error(f"Agent error: type={agent_type}, error={e}")
        return {
            "type": "error",
            "content": f"Agent processing failed: {e}",
            "reasoning": None,
            "confidence": "low",
            "agent": f"DeepAgent[{agent_type}]",
            "error": str(e),
        }


def _extract_tool_calls(messages: list[Any]) -> list[dict[str, Any]]:
    """Extract tool call information from agent messages for audit trail."""
    tool_calls = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "name": tc.get("name", "unknown"),
                    "args": tc.get("args", {}),
                })
    return tool_calls
