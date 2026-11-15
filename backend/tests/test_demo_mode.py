"""Pure tests for DEMO_MODE response replay (issue #2).

Same philosophy as test_github_provider: no network, no DB, no fixtures —
craft prompts, call the selector, assert the contract each caller's parser
depends on (the JSON shapes groq_json/extract_json must be able to read, the
determinism of the prompt-hash bucketing, and the zero-key replay through the
groq_chat choke point).
"""

import asyncio

from app.config import settings
from app.integrations.demo_llm import demo_completion
from app.services.groq_client import extract_json, groq_chat


def msg(prompt: str, system: str = "You are a helpful assistant.") -> list[dict]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]


# Prompt fragments copied from the real callers — the markers the selector
# keys on must stay in sync with what the services actually send.
STANDUP = "Analyze today's standup. For each team member I provide yesterday/today/blockers."
BLOCKERS = "Blocked or stuck work items from Azure DevOps (facts, do not change them):"
PLAN = "Plan Sprint 2404.\n\nCandidate backlog items (pick only from these, by 'item'):"
RELEASE = "Release readiness facts (computed, do not change the status):"
BRIEF = "Write the morning brief for 2026-11-15 from the live delivery data below."
TRIAGE = "Decide whether this task is suitable for an autonomous AI coding agent."
ASK_SYSTEM = (
    "You are the delivery manager for this organization, answering a busy executive."
)


def test_each_agent_kind_replays_parseable_json_with_expected_shape():
    shapes = {
        STANDUP: ({"blockers", "risks", "recommendations", "summary"}, list),
        BLOCKERS: ({"actions", "recommendations", "summary"}, dict),
        PLAN: ({"sprintGoal", "proposedItems", "recommendations"}, list),
        RELEASE: ({"recommendation"}, str),
        BRIEF: (
            {"headline", "shipped", "ai_delivered", "risks", "needs_decision", "numbers", "narrative"},
            str,
        ),
        TRIAGE: ({"suitable", "confidence", "reason"}, str),
    }
    for prompt, (keys, blockers_type) in shapes.items():
        data = extract_json(demo_completion(msg(prompt)))
        missing = keys - data.keys()
        assert not missing, f"{prompt[:30]}... missing keys: {missing}"
        if prompt == STANDUP:
            for b in data["blockers"]:
                assert {"member", "issue", "severity", "suggestedAction"} <= b.keys()
                assert b["severity"] in ("High", "Medium", "Low")
        if prompt == BLOCKERS:
            assert isinstance(data["actions"], blockers_type)
        if prompt == TRIAGE:
            assert data["suitable"] in (True, False)
            assert data["confidence"] in ("low", "medium", "high")


def test_ask_questions_get_markdown_not_json():
    for q in ("What should I worry about this week?", "Who is blocked?"):
        out = demo_completion(msg(q, ASK_SYSTEM))
        assert out and not out.lstrip().startswith("{")
        assert "**" in out and "\n-" in out  # executive-tone markdown


def test_selection_is_deterministic_but_varies_by_prompt():
    for prompt in (STANDUP, ASK_SYSTEM, TRIAGE):
        base = demo_completion(msg(prompt + " seed"))
        assert demo_completion(msg(prompt + " seed")) == base
    standups = {
        demo_completion(msg(f"{STANDUP} round {i}")) for i in range(12)
    }
    asks = {
        demo_completion(msg(f"question number {i}", ASK_SYSTEM)) for i in range(12)
    }
    assert len(standups) > 1 and len(asks) > 1  # repeat asks feel alive


def test_groq_chat_replays_without_any_api_key():
    was_demo, was_key = settings.demo_mode, settings.groq_api_key
    settings.demo_mode, settings.groq_api_key = True, ""
    try:
        content = asyncio.run(groq_chat(msg(STANDUP)))
        assert "summary" in extract_json(content)
        assert asyncio.run(groq_chat(msg("How is the sprint going?", ASK_SYSTEM)))
    finally:
        settings.demo_mode, settings.groq_api_key = was_demo, was_key


def test_demo_responses_stay_in_the_fictional_world():
    corpus = "\n".join(
        demo_completion(msg(p))
        for p in (STANDUP, BLOCKERS, PLAN, RELEASE, BRIEF, TRIAGE)
    ) + "\n".join(demo_completion(msg(f"q{i}", ASK_SYSTEM)) for i in range(3))
    assert "2403" in corpus or "Storefront" in corpus or "Loyalty" in corpus
    for real in ("Microsoft", "Azure OpenAI", "OpenAI, Inc", "Groq"):
        assert real not in corpus
