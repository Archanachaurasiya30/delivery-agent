"""What happens in the real world when a human approves a proposal.

Azure DevOps is read-only for this deployment (PUSH_ENABLED=false), so
"executing" never writes to ADO. What it does:

- blocker_detection: DMs each blocked item's owner on Webex with the item,
  the suggested action and a link — the escalation actually reaches a person.
- sprint_planning: produces the ready-to-apply checklist (one ADO link per
  item) so applying the plan in ADO is a click-through, not a re-typing job.

Every outcome (sent / skipped / failed, per person) lands in
``execution_result`` so the audit trail shows exactly what happened.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.integrations.webex_client import (
    WebexClient,
    WebexError,
    WebexRecipientError,
    can_deliver,
)
from app.models.proposal import Proposal

logger = logging.getLogger(__name__)


def _report(proposal: Proposal) -> dict[str, Any]:
    content = proposal.content or {}
    report = content.get("report")
    return report if isinstance(report, dict) else {}


async def _notify_blocker_owners(proposal: Proposal, approver: str) -> dict[str, Any]:
    blockers = [b for b in _report(proposal).get("blockers", []) if isinstance(b, dict)]
    if not settings.webex_bot_token:
        return {"action": "notify_owners", "sent": [], "skipped": [],
                "note": "Webex is not configured (WEBEX_BOT_TOKEN) — nobody was notified."}

    # One message per person, listing all of their items.
    by_email: dict[str, list[dict[str, Any]]] = {}
    skipped: list[str] = []
    for b in blockers:
        email = b.get("email")
        if not can_deliver(email):
            skipped.append(f"{b.get('member', 'Unassigned')}: no Webex email on record")
            continue
        by_email.setdefault(email, []).append(b)

    client = WebexClient(settings.webex_bot_token, base_url=settings.webex_api_base)
    sent: list[str] = []
    failed: list[str] = []
    for email, items in by_email.items():
        lines = [f"Hi {items[0].get('member', '')} — {approver} flagged these as blocked. "
                 "What do you need to move them?"]
        for b in items:
            link = f"[{b.get('item')}]({b['url']})" if b.get("url") else b.get("item")
            lines.append(f"- **{link}** {b.get('title', '')} — {b.get('description', '')}")
            if b.get("suggestedAction"):
                lines.append(f"  - Suggested: {b['suggestedAction']}")
        try:
            await client.send_to_email(email, "\n".join(lines))
            sent.append(email)
        except WebexRecipientError:
            skipped.append(f"{email}: not reachable on Webex")
        except (WebexError, Exception) as exc:  # noqa: BLE001 - report, don't crash the approval
            logger.warning("Blocker notification to %s failed: %s", email, exc)
            failed.append(f"{email}: {exc}")
    result = {"action": "notify_owners", "sent": sent, "skipped": skipped, "failed": failed}
    if settings.webex_redirect_to:
        result["note"] = f"Test mode: every message went to {settings.webex_redirect_to}, not to the owners."
    return result


def _sprint_checklist(proposal: Proposal) -> dict[str, Any]:
    report = _report(proposal)
    items = [
        {"item": p.get("id"), "title": p.get("title"), "url": p.get("url")}
        for p in report.get("proposedItems", []) if isinstance(p, dict)
    ]
    return {
        "action": "apply_in_ado",
        "targetSprint": report.get("targetSprint"),
        "items": items,
        "note": "Azure DevOps is read-only from here: move these items into the sprint in ADO "
                "(links included). The next sync will pick the change up.",
    }


async def execute(proposal: Proposal, approver: str) -> None:
    """Run the side effect for an approved proposal. Never raises."""
    try:
        if proposal.type == "blocker_detection":
            result = await _notify_blocker_owners(proposal, approver)
            if result.get("sent"):
                proposal.state = "executed"
        elif proposal.type == "sprint_planning":
            result = _sprint_checklist(proposal)
        else:
            return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Executing proposal %s failed", proposal.id)
        result = {"error": str(exc)}
    result["executed_at"] = datetime.now(timezone.utc).isoformat()
    proposal.execution_result = {**(proposal.execution_result or {}), **result}
