"""Seed the database with a clean, realistic demo dataset.

Wipes the working tables (FK-safe order) and inserts a curated set of team
members, tasks, streams, active sprints, a backfilled release-confidence trend,
and example proposals (including a cross-stream escalation) so the app boots
with coherent, persisted data instead of empty Phase 1 views.

Run inside the backend container:

    docker exec delivery-agent-backend python -m app.seed
"""

import asyncio
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.database import async_session_maker
from app.models.agent_run import AgentRun
from app.models.confidence import ConfidenceSnapshot
from app.models.feature import Feature
from app.models.proposal import Proposal
from app.models.sprint import Sprint
from app.models.standup import StandupEntry, StandupRound
from app.models.stream import Stream
from app.models.task import Task
from app.models.team import TeamMember

# (full name, short name used on tasks, team, role)
MEMBERS = [
    ("Sarah Chen", "Sarah", "Platform", "tech_lead"),
    ("Diego Alvarez", "Diego Alvarez", "Platform", "developer"),
    ("Priya Nair", "Priya Nair", "Platform", "developer"),
    ("Tomás Silva", "Tomás Silva", "Mobile", "developer"),
    ("Emma Fischer", "Emma Fischer", "Mobile", "developer"),
    ("Jonah Klein", "Jonah Klein", "Mobile", "developer"),
    ("Aisha Rahman", "Aisha Rahman", "Quality", "qa"),
]

# (external_id, title, status, assignee short name, story_points)
# Statuses are tuned so live confidence agrees with the backfilled trend:
# Storefront (4101-107, 112-114, 116-117, 120-121) burns down healthily
# (mostly done) while Loyalty & Infra lags (mostly todo + a blocker).
TASKS = [
    (4101, "Storefront Full test Cycle 6", "done", "Sarah", 26),
    (4103, "O1 - As a system, I want to create a section in the storefront catalog", "done", "Diego Alvarez", 8),
    (4104, "O2 - As a Storefront user, I want to be able to share a cart with another Storefront user", "done", "Priya Nair", 12),
    (4105, "O3 - As a Storefront user, I want to receive order status updates", "done", "Tomás Silva", 6),
    (4106, "O4 - As a Storefront user, I want to know the status of the orders I placed", "done", "Emma Fischer", 4),
    (4107, "O5 - As a Storefront user, I want to know the status of my delivery", "in_progress", "Jonah Klein", 8),
    (4108, "Refactor and Create automation test cases Phase 10", "todo", "Aisha Rahman", 20),
    (4109, "TP001 - [Loyalty] Update DAL for all get services", "in_progress", "Sarah", 16),
    (4110, "TP002 - [Pulse] Documentation for CDN suggested solution", "todo", "Diego Alvarez", 4),
    (4111, "TP003 - [Pulse] POC for CDN suggested solution", "todo", "Priya Nair", 15),
    (4112, "O1.1 - As a Storefront User, I want to send a group order invite to another Storefront user", "done", "Tomás Silva", 8),
    (4113, "O1.3 - As a Storefront iOS user, I want to be able to select saved addresses", "done", "Emma Fischer", 6),
    (4114, "O1.2 - As a Storefront user, I want to invite another user from my device contacts", "review", "Jonah Klein", 10),
    (4115, "Move EF migration to be a separated project", "in_progress", "Aisha Rahman", 12),
    (4116, "Support sending silent order notifications", "in_progress", "Sarah", 4),
    (4117, "Add flag to notifications to show order hold status", "done", "Diego Alvarez", 4),
    (4118, "Update the projects to use Redis Sentinel", "todo", "Priya Nair", 8),
    (4119, "Send logs to Elastic", "todo", "Tomás Silva", 12),
    (4120, "Use dynamic templates to trigger order actions", "in_progress", "Emma Fischer", 20),
    (4121, "Order number generator on DB", "todo", "Jonah Klein", 14),
    (4122, "Review and prepare to merge V0 to development", "done", "Aisha Rahman", 8),
    (4123, "Optimize Loyalty Points Initial Load with Progressive Fetching", "done", "Sarah", 16),
    (4124, "Security audit for release 2.0", "review", "Aisha Rahman", 24),
]

# Which tasks belong to which stream's active sprint (by external_id).
MESSAGING_IDS = {
    4101, 4103, 4104, 4105, 4106, 4107,
    4112, 4113, 4114, 4116, 4117, 4120, 4121,
}
CALENDAR_IDS = {
    4108, 4109, 4110, 4111, 4115,
    4118, 4119, 4122, 4123, 4124,
}
# In-progress tasks backdated past the 3-day threshold so the blocker heuristic
# flags them (drags the Loyalty & Infra stream's confidence down).
BLOCKER_IDS = {4109}

# Features group tasks within a stream (the "what"). feature name -> external_ids.
MESSAGING_FEATURES = {
    "Core Storefront": {4101, 4103, 4104, 4105, 4106, 4107, 4112, 4113, 4114},
    "Notifications": {4116, 4117, 4120, 4121},
}
CALENDAR_FEATURES = {
    "Loyalty Services": {4108, 4109, 4122, 4123},
    "Infra & Release 2.0": {4110, 4111, 4115, 4118, 4119, 4124},
}


def _email(short: str) -> str:
    slug = short.lower().replace(" ", "").replace(".", "")
    return f"{slug}@delivery.local"


def _backfill_snapshots(
    sprint_id: str, start_value: float, end_value: float, ahead_on_last: bool
) -> list[ConfidenceSnapshot]:
    """Build 14 daily snapshots ramping linearly start_value -> end_value.

    Inserted directly (not via the live service) so the demo trend shape is
    deterministic and the sparkline / direction slope are non-trivial.
    """
    today = date.today()
    span = 14
    snaps: list[ConfidenceSnapshot] = []
    for i in range(span):
        day = today - timedelta(days=span - 1 - i)  # today-13 .. today
        value = round(start_value + (end_value - start_value) * i / (span - 1), 1)
        is_last = i == span - 1
        snaps.append(
            ConfidenceSnapshot(
                sprint_id=sprint_id,
                snapshot_date=day,
                confidence_value=value,
                # Keep the four factors == value so the card's bars read coherently.
                scope_remaining=value,
                velocity_vs_plan=value,
                open_blockers=value,
                untested_surface=value,
                factors={"schedule_ahead": bool(ahead_on_last and is_last)},
            )
        )
    return snaps


async def seed() -> None:
    async with async_session_maker() as session:
        # Wipe in FK-safe order (children before parents).
        await session.execute(delete(StandupEntry))
        await session.execute(delete(StandupRound))
        await session.execute(delete(ConfidenceSnapshot))
        await session.execute(delete(AgentRun))  # references tasks + proposals
        await session.execute(delete(Task))
        await session.execute(delete(Feature))  # referenced by tasks
        await session.execute(delete(Proposal))
        await session.execute(delete(Sprint))
        await session.execute(delete(Stream))
        await session.execute(delete(TeamMember))
        await session.flush()

        # Members, keyed by short name so tasks can resolve assignee_id.
        short_to_id: dict[str, str] = {}
        for full_name, short, _team, role in MEMBERS:
            member = TeamMember(
                name=full_name,
                email=_email(short),
                role=role,
                capacity_hours_per_sprint=40,
                is_available=True,
            )
            session.add(member)
            await session.flush()  # populate member.id
            short_to_id[short] = member.id

        # Streams (status/direction are derived, never stored here).
        messaging = Stream(
            name="Storefront",
            description="Customer storefront: cart, checkout, order status, notifications.",
            owner_id=short_to_id["Sarah"],
        )
        calendar = Stream(
            name="Loyalty & Infra",
            description="Loyalty services, CDN, infra hardening, release 2.0 audit.",
            owner_id=short_to_id["Aisha Rahman"],
        )
        session.add_all([messaging, calendar])
        await session.flush()  # populate stream ids

        # Features per stream (the "what"); build external_id -> feature_id.
        ext_to_feature_id: dict[int, str] = {}
        for stream, feature_groups in (
            (messaging, MESSAGING_FEATURES),
            (calendar, CALENDAR_FEATURES),
        ):
            for name, ext_ids in feature_groups.items():
                feature = Feature(name=name, stream_id=stream.id)
                session.add(feature)
                await session.flush()  # populate feature.id
                for ext_id in ext_ids:
                    ext_to_feature_id[ext_id] = feature.id

        # One active sprint per stream, straddling today (so burndown has a
        # 'today' point and the daily job has live work to snapshot).
        today = date.today()
        messaging_sprint = Sprint(
            name="Storefront Sprint 2403",
            goal="Ship the core storefront path (O1-O5) to review.",
            start_date=today - timedelta(days=7),
            end_date=today + timedelta(days=7),
            status="active",
            capacity_hours=240,
            stream_id=messaging.id,
        )
        calendar_sprint = Sprint(
            name="Loyalty Sprint 2403",
            goal="Land loyalty DAL + infra prerequisites for release 2.0.",
            start_date=today - timedelta(days=7),
            end_date=today + timedelta(days=7),
            status="active",
            capacity_hours=200,
            stream_id=calendar.id,
        )
        session.add_all([messaging_sprint, calendar_sprint])
        await session.flush()  # populate sprint ids

        # Tasks, assigned to the matching stream's sprint.
        blocker_backdate = datetime.now(timezone.utc) - timedelta(days=5)
        for external_id, title, status_, assignee_short, points in TASKS:
            if external_id in MESSAGING_IDS:
                sprint_id = messaging_sprint.id
            elif external_id in CALENDAR_IDS:
                sprint_id = calendar_sprint.id
            else:
                sprint_id = None
            task = Task(
                title=title,
                status=status_,
                priority="medium",
                assignee_id=short_to_id.get(assignee_short),
                story_points=points,
                external_id=str(external_id),
                source="local",
                sprint_id=sprint_id,
                feature_id=ext_to_feature_id.get(external_id),
            )
            # Backdate selected in-progress tasks so they count as blockers.
            if external_id in BLOCKER_IDS:
                task.updated_at = blocker_backdate
            session.add(task)

        # Backfilled daily confidence trend: Storefront improving -> Ahead,
        # Loyalty declining -> Behind.
        snapshots = (
            _backfill_snapshots(messaging_sprint.id, 55.0, 78.0, ahead_on_last=True)
            + _backfill_snapshots(calendar_sprint.id, 70.0, 48.0, ahead_on_last=False)
        )
        session.add_all(snapshots)

        # Operational (project-scope) proposals — these belong to a single PM's
        # queue and must NOT appear at portfolio level.
        project_proposals = [
            Proposal(
                type="task_rebalance",
                state="pending_review",
                scope="project",
                stream_id=messaging.id,
                confidence="medium",
                reasoning="O4 (order status) has sat in review; pair Emma Fischer with Sarah to clear it before pulling O5.",
                content={"action": "reassign_review", "task": "O4 - status of orders", "to": "Sarah"},
                created_by_agent="planning-agent",
            ),
            Proposal(
                type="blocker_resolution",
                state="pending_review",
                scope="project",
                stream_id=messaging.id,
                confidence="low",
                reasoning="Silent order notifications (4116) is unestimated; split into a spike + impl before committing it to the sprint.",
                content={"action": "split", "task": "Support sending silent order notifications"},
                created_by_agent="planning-agent",
            ),
            Proposal(
                type="scope_cut",
                state="pending_review",
                scope="project",
                stream_id=calendar.id,
                confidence="high",
                reasoning="TP003 CDN POC (4111) is low-confidence and off the release-2.0 critical path; defer it to protect the security audit.",
                content={"action": "defer", "task": "TP003 - POC for CDN suggested solution"},
                created_by_agent="planning-agent",
            ),
            Proposal(
                type="blocker_resolution",
                state="pending_review",
                scope="project",
                stream_id=calendar.id,
                confidence="medium",
                reasoning="TP001 Loyalty DAL (4109) has been in progress 5 days — likely blocked on the EF migration split (4115). Sequence 4115 first.",
                content={"action": "sequence", "before": "Move EF migration", "then": "TP001 - Update DAL"},
                created_by_agent="planning-agent",
            ),
        ]

        # Escalations — above a single PM's altitude; surface ONLY at portfolio.
        escalations = [
            Proposal(
                type="cross_stream_dependency",
                state="pending_review",
                scope="portfolio",
                escalated=True,
                stream_id=None,  # cross-stream: belongs to no single PM queue
                confidence="medium",
                reasoning=(
                    "Release 2.0's security audit (Loyalty & Infra) needs iOS review bandwidth "
                    "that only Emma Fischer has — currently on Storefront. Moving her for one "
                    "sprint slips Storefront's O1.3 but de-risks the audit. Cross-stream call."
                ),
                content={
                    "move": "Emma Fischer",
                    "from": "Storefront",
                    "to": "Loyalty & Infra",
                    "duration": "1 sprint",
                },
                created_by_agent="portfolio-agent",
            ),
            Proposal(
                type="release_slip",
                state="pending_review",
                scope="stream",
                escalated=True,
                stream_id=calendar.id,
                confidence="high",
                reasoning=(
                    "Loyalty & Infra release 2.0 will slip ~1 week given open audit findings. "
                    "Accepting the slip vs. cutting audit scope exceeds the PM — escalating for a call."
                ),
                content={"stream": "Loyalty & Infra", "slip": "~1 week", "alternative": "cut audit scope"},
                created_by_agent="portfolio-agent",
            ),
        ]
        session.add_all(project_proposals + escalations)

        await session.commit()

        members_count = await session.scalar(select(func.count()).select_from(TeamMember))
        tasks_count = await session.scalar(select(func.count()).select_from(Task))
        streams_count = await session.scalar(select(func.count()).select_from(Stream))
        features_count = await session.scalar(select(func.count()).select_from(Feature))
        sprints_count = await session.scalar(select(func.count()).select_from(Sprint))
        snaps_count = await session.scalar(select(func.count()).select_from(ConfidenceSnapshot))
        proposals_count = await session.scalar(select(func.count()).select_from(Proposal))
        escalated_count = await session.scalar(
            select(func.count()).select_from(Proposal).where(
                Proposal.scope.in_(["stream", "portfolio"])
            )
        )
        print(
            f"✓ Seeded {members_count} members, {tasks_count} tasks, "
            f"{streams_count} streams, {features_count} features, "
            f"{sprints_count} sprints, "
            f"{snaps_count} confidence snapshots, {proposals_count} proposals "
            f"({escalated_count} escalations)."
        )


if __name__ == "__main__":
    asyncio.run(seed())
