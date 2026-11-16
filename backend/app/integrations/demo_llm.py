"""Pre-recorded agent responses for DEMO_MODE (issue #2).

Every LLM-backed agent loop in the app (analysis proposals, standup digests,
morning briefs, autopilot triage, ask-the-DM) funnels through
``services.groq_client.groq_chat``. When ``DEMO_MODE=true`` that choke point
replays one of the recorded responses below instead of calling an API, so the
full UI experience runs with zero API keys.

All content is set in the fictional Northwind Dynamics world (sprint 2403,
Storefront + Loyalty & Infra streams, task ids 41xx) — no real people or
companies. Selection is deterministic per prompt (sha256 bucket), so repeat
asks feel alive but reproducible without a key.
"""

import hashlib
import json

# ---------------------------------------------------------------- standup
_STANDUP = [
    {
        "blockers": [
            {
                "member": "Sarah Chen",
                "issue": "Loyalty DAL update (#4109) is waiting on a data-platform code review",
                "severity": "Medium",
                "suggestedAction": "Sarah to ping the data-platform channel before noon; escalate at the sprint 2403 sync if silent.",
            },
            {
                "member": "Jonah Klein",
                "issue": "Delivery-status work (#4107) is waiting for sandbox credentials",
                "severity": "High",
                "suggestedAction": "Ask Tomás Silva to share the workaround he used for the storefront integration.",
            },
        ],
        "risks": [
            "Loyalty & Infra is slipping — three items still in progress with sprint 2403 closing this week.",
            "Group-order review (#4114) has been in review longer than usual.",
        ],
        "recommendations": [
            "Rebalance one Loyalty & Infra item to Priya Nair; her Storefront load is light.",
            "Emma Fischer to pick up the dynamic-templates review (#4120) today.",
            "Leave Aisha Rahman's automation cycle (#4108) untouched — it protects the release.",
        ],
        "summary": "Storefront is tracking well to close sprint 2403; Loyalty & Infra is the pressure point with two dependency-blocked items. The data-platform review needs an owner today.",
    },
    {
        "blockers": [
            {
                "member": "Diego Alvarez",
                "issue": "CDN documentation (#4110) is blocked on the final architecture decision from the infra review",
                "severity": "Low",
                "suggestedAction": "Chase the infra review notes in Wednesday's session; nothing else needed today.",
            }
        ],
        "risks": [
            "Priya Nair's CDN proof of concept (#4111) is the largest untouched item left in the sprint.",
        ],
        "recommendations": [
            "Split the CDN POC into a spike plus implementation so progress is visible.",
            "Jonah Klein to close out order status (#4107) before pulling new work.",
        ],
        "summary": "A quiet standup: Storefront keeps burning down and only the CDN decision holds up Loyalty & Infra. No people risks; capacity looks balanced for the sprint 2403 close.",
    },
    {
        "blockers": [],
        "risks": [
            "Order-number generator (#4121) is unestimated and sitting in todo late in the sprint.",
        ],
        "recommendations": [
            "Jonah Klein to estimate #4121 today so next-sprint planning can count it.",
            "Sarah Chen to run a mid-week checkpoint on the Loyalty & Infra stream.",
        ],
        "summary": "Clean standup across Storefront and Loyalty & Infra — no blockers reported. One unestimated item is the only planning smell heading into the sprint 2403 close.",
    },
]

# ------------------------------------------------- blocker-detection agent
_BLOCKERS = [
    {
        "actions": {
            "#4109": "Ask Sarah Chen to set a 24h deadline with the data-platform reviewers; if it slips again, move #4109 to the next sprint and re-plan the Loyalty DAL batch.",
            "#4107": "Jonah Klein needs sandbox credentials — Sarah Chen should request them from platform ops today.",
            "#4115": "Pair Aisha Rahman with Diego Alvarez for an afternoon; the EF migration split is mechanical once the project layout is agreed.",
        },
        "recommendations": [
            "Run a daily 15-minute unblock huddle on Loyalty & Infra until the three in-progress items move.",
            "Cap Storefront WIP: the stream is ahead, so don't pull new items while reviews (#4114) pile up.",
        ],
        "summary": "Most blocked time sits in Loyalty & Infra and is dependency-shaped, not capability-shaped. Two chase-today actions unblock the majority of the stuck hours.",
    },
    {
        "actions": {
            "#4114": "Emma Fischer and Jonah Klein are both touching group orders — ask Sarah Chen to make Jonah sole owner for review sign-off.",
            "#4120": "The dynamic-templates work has been in progress the longest; ask Emma Fischer to demo what exists in tomorrow's standup.",
        },
        "recommendations": [
            "Add a 'blocked more than 3 days' review at the sprint 2403 close.",
            "Keep one reviewer (Priya Nair) unbooked each afternoon for the Storefront review queue.",
        ],
        "summary": "Blockers are few and concentrated in review hand-offs rather than deep technical risk. Clearing the review queue recovers the most days.",
    },
]

# ---------------------------------------------------- sprint-planning agent
_SPRINT_PLAN = [
    {
        "sprintGoal": "Close the remaining Storefront order-status journeys and unblock the Loyalty & Infra DAL work.",
        "proposedItems": [
            {"item": "#4107", "priority": "High", "reason": "Last open order-status story; Jonah Klein is already deep in it."},
            {"item": "#4108", "priority": "High", "reason": "Aisha Rahman's automation cycle protects the release train."},
            {"item": "#4110", "priority": "Medium", "reason": "Small documentation task that de-risks the CDN decision for Loyalty & Infra."},
            {"item": "#4118", "priority": "Medium", "reason": "The Redis Sentinel upgrade is self-contained infra work for Priya Nair."},
            {"item": "#4121", "priority": "Medium", "reason": "Order-number generator unblocks storefront scaling; needs an estimate first."},
        ],
        "recommendations": [
            "Hold the CDN POC (#4111) for one sprint — it depends on the #4110 architecture decision.",
            "Keep Diego Alvarez 60% committed so he can absorb Loyalty & Infra spillover.",
        ],
    },
    {
        "sprintGoal": "Stabilise Loyalty & Infra while Storefront finishes its remaining review items.",
        "proposedItems": [
            {"item": "#4115", "priority": "High", "reason": "The EF migration split gates the Loyalty DAL batch; Aisha Rahman already started."},
            {"item": "#4107", "priority": "High", "reason": "Completes the order-status journey users keep asking about."},
            {"item": "#4119", "priority": "Medium", "reason": "Elastic logging is contained and helps both streams."},
            {"item": "#4120", "priority": "Medium", "reason": "Dynamic templates are mostly done — finishing beats restarting."},
        ],
        "recommendations": [
            "Balance streams: two Storefront and two Loyalty & Infra items keeps both release trains moving.",
            "Ask Sarah Chen to time-box the #4109 dependency chase to one day.",
        ],
    },
]

# ------------------------------------------------- release-management agent
_RELEASE = [
    {
        "recommendation": (
            "Go, with one condition: land #4107 and clear the #4114 review before the sprint 2403 "
            "cut-off on Friday. The Loyalty & Infra spillover (#4109, #4115) is infrastructure "
            "work, not user-facing — shipping the Storefront release without it is acceptable, but "
            "chase the data-platform reviewers today so it doesn't roll two sprints."
        )
    },
    {
        "recommendation": (
            "No-go as it stands: the review queue (#4114, #4120) is the release content and both "
            "items are moving slowly. Give Jonah Klein and Emma Fischer a clear day each with no "
            "interrupts and re-assess Thursday; if both merge, release with the Loyalty & Infra "
            "work deferred to the next sprint."
        )
    },
]

# ---------------------------------------------------------- morning brief
_BRIEF = [
    {
        "headline": "Storefront is closing sprint 2403 strong while Loyalty & Infra waits on one external review.",
        "shipped": [
            "Order-status journeys finished (#4105, #4106)",
            "Group-order invites merged for iOS (#4112, #4113)",
        ],
        "ai_delivered": [
            "Autonomous agent completed the notification-flag change (#4117) with tests green",
            "Agent triage queued two backlog candidates for the next sprint",
        ],
        "risks": [
            "Loyalty DAL batch (#4109) blocked on a data-platform review for three days",
            "Portfolio confidence dipped two points on the Loyalty & Infra stream",
        ],
        "needs_decision": [
            "Defer the CDN proof of concept (#4111) one sprint, or book a dedicated spike?",
        ],
        "numbers": {
            "Portfolio confidence": "72%",
            "Sprint 2403 completion": "68%",
            "Blocked items": "2",
            "AI tasks shipped (7d)": "3",
        },
        "narrative": (
            "Sprint 2403 is on track for the Storefront release train: the order-status journeys "
            "are done and reviews are clearing. The pressure point is Loyalty & Infra, where a "
            "single external dependency has stalled three items. One decision is needed today — "
            "whether the CDN proof of concept waits another sprint. The AI workforce continues to "
            "absorb small, well-specified tasks without pulling reviewer time."
        ),
    },
    {
        "headline": "Quiet day: reviews cleared, one blocker left, and the AI workforce shipped the logging groundwork.",
        "shipped": [
            "Saved-address selection shipped on iOS (#4113)",
            "V0 merge preparation completed (#4122)",
        ],
        "ai_delivered": [
            "Agent drafted the Elastic logging scaffold for #4119 — awaiting human review",
            "Nightly triage found no new agent-suitable tasks",
        ],
        "risks": [
            "Order-number generator (#4121) is unestimated with planning imminent",
        ],
        "needs_decision": [
            "Approve the rebalance proposal moving one Loyalty & Infra item to Priya Nair",
        ],
        "numbers": {
            "Portfolio confidence": "74%",
            "Sprint 2403 completion": "71%",
            "Blocked items": "1",
            "AI tasks in flight": "1",
        },
        "narrative": (
            "The board is healthier than yesterday: Storefront reviews cleared and only the CDN "
            "decision still blocks Loyalty & Infra. The single open decision is a small rebalance "
            "that protects the sprint close. Estimating #4121 before planning keeps the next "
            "sprint honest."
        ),
    },
]

# ------------------------------------------------------- autopilot triage
_TRIAGE = [
    {
        "suitable": True,
        "confidence": "high",
        "reason": "Small, well-specified change with clear acceptance criteria and no cross-team dependencies.",
    },
    {
        "suitable": False,
        "confidence": "medium",
        "reason": "Needs a product decision on scope before any code is written; better with a human owner.",
    },
    {
        "suitable": True,
        "confidence": "medium",
        "reason": "Mechanical refactor with tests described; the agent should pair the diff with Aisha Rahman's QA checklist.",
    },
]

# ------------------------------------------------------- release notes
# Markdown (not JSON) — the sprint_service passes the sprint's done items and
# expects a shareable changelog back.
_RELEASE_NOTES = [
    (
        "## Sprint 2403 — Storefront\n\n"
        "Storefront closed out the order-status journeys and the group-order "
        "rollout reached iOS, while the AI workforce shipped its first "
        "customer-visible change.\n\n"
        "### Features\n"
        "- Completed the order-status journeys (#4105, #4106) — Storefront\n"
        "- Group-order invites merged for iOS (#4112, #4113) — Storefront\n"
        "- Dynamic order templates for confirmation mails (#4120) — Storefront\n\n"
        "### Bug fixes\n"
        "- Notification-flag regression fixed by the autonomous agent, tests "
        "green (#4117) — Storefront\n\n"
        "### Other\n"
        "- Elastic logging scaffold drafted for #4119 — Loyalty & Infra\n"
    ),
    (
        "## Sprint 2403 — Storefront\n\n"
        "A release focused on finishing: the remaining storefront journeys "
        "landed and the automation cycle protected the release train.\n\n"
        "### Features\n"
        "- Order-status journeys shipped end to end (#4105, #4106) — Storefront\n"
        "- Saved-address selection shipped on iOS (#4113) — Storefront\n\n"
        "### Bug fixes\n"
        "- Group-order invite edge cases fixed ahead of the iOS merge "
        "(#4112) — Storefront\n\n"
        "### Other\n"
        "- Release-automation cycle completed (#4108) — Loyalty & Infra\n"
    ),
]

# ------------------------------------------------------- ask-the-DM answers
_ASK = [
    (
        "**Sprint 2403 is on track overall — Storefront is green, Loyalty & Infra is the watch "
        "item.**\n"
        "- Storefront is roughly 70% complete: the order-status journeys are done and two items "
        "remain in review.\n"
        "- Loyalty & Infra has two blocked items, both waiting on the same data-platform review.\n"
        "- Portfolio confidence sits at 72%, down two points this week, driven entirely by the "
        "Loyalty & Infra stream.\n"
        "- The one decision waiting on you: defer the CDN proof of concept (#4111) one sprint, "
        "or book a dedicated spike."
    ),
    (
        "**Your biggest risk is review throughput, not delivery.**\n"
        "- The remaining sprint content is sitting in review (#4114, #4120) rather than in "
        "progress.\n"
        "- Jonah Klein and Emma Fischer own all of it; neither has a free afternoon this week.\n"
        "- Clearing the queue recovers an estimated three days of cycle time before the release "
        "cut-off.\n"
        "- Suggested action: protect one reviewer-day each and freeze new Storefront work until "
        "the queue is empty."
    ),
    (
        "**The AI workforce is earning its keep without adding risk.**\n"
        "- Three agent-completed tasks shipped in the last seven days, all with tests green on "
        "the first CI pass.\n"
        "- Two backlog candidates are queued for tonight's triage; both look well-specified.\n"
        "- Agent work is capped at small, single-stream changes — nothing has needed a human "
        "rescue this sprint.\n"
        "- Nothing needs your decision here; the autopilot daily limit of five is nowhere near "
        "binding."
    ),
]

# Marker (lowercased substring) -> variants, first match wins. Anything that
# matches no marker is an ask-the-DM style question.
_KINDS: tuple[tuple[str, list], ...] = (
    ("analyze today's standup", _STANDUP),
    ("blocked or stuck work items", _BLOCKERS),
    ("candidate backlog items", _SPRINT_PLAN),
    ("release readiness facts", _RELEASE),
    ("draft release notes", _RELEASE_NOTES),
    ("morning brief", _BRIEF),
    ("autonomous ai coding agent", _TRIAGE),
)


def demo_completion(messages: list[dict]) -> str:
    """Pick the recorded response for this conversation (deterministic).

    The prompt text is hashed to bucket it into one of the kind's variants, so
    the same ask always replays the same answer while different asks vary.
    JSON kinds return raw JSON text (``groq_json``/``extract_json`` parse it);
    ask-style prompts return markdown.
    """
    text = "\n".join(str(m.get("content") or "") for m in messages)
    lowered = text.lower()
    variants = next(
        (v for marker, v in _KINDS if marker in lowered),
        _ASK,
    )
    pick = variants[hashlib.sha256(text.encode("utf-8")).digest()[0] % len(variants)]
    return pick if isinstance(pick, str) else json.dumps(pick)
