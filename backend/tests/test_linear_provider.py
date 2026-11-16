"""Pure mapping + fake-transport tests for the Linear provider.

Same philosophy as test_jira_provider: no network, no fixtures — feed
crafted GraphQL issue nodes into the mapper and assert the contract the
import layer depends on. The status mapping (state.type + review-status
override) is the public interface to anyone pointing the app at a Linear
workspace; these tests are its spec.
"""

import asyncio
import json

import pytest

from app.integrations.linear_task_provider import (
    DEFAULT_REVIEW_STATUSES,
    LinearTaskProvider,
    _pick_state,
)
from app.integrations.task_provider import ExternalTaskCreate, ExternalTaskUpdate

P = LinearTaskProvider(api_key="k")


def node(**over):
    base = {
        "id": "uuid-42",
        "identifier": "ENG-42",
        "title": "Fix checkout",
        "description": None,
        "priority": 3,
        "updatedAt": "2026-11-16T09:00:00.000Z",
        "estimate": None,
        "state": {"name": "Todo", "type": "unstarted"},
        "assignee": None,
        "team": {"id": "team-1", "key": "ENG"},
        "cycle": None,
        "labels": {"nodes": []},
    }
    base.update(over)
    return base


def test_state_types():
    assert P._map_issue(node(state={"name": "Backlog", "type": "backlog"})).status == "backlog"
    assert P._map_issue(node(state={"name": "Todo", "type": "unstarted"})).status == "todo"
    assert P._map_issue(node(state={"name": "In Progress", "type": "started"})).status == "in_progress"
    assert P._map_issue(node(state={"name": "Done", "type": "completed"})).status == "done"
    # canceled is closed, not active — boards as done
    assert P._map_issue(node(state={"name": "Canceled", "type": "canceled"})).status == "done"


def test_review_state_name_overrides_type():
    t = P._map_issue(node(state={"name": "In Review", "type": "started"}))
    assert t.status == "review"
    # Custom list replaces the default, not extends it.
    custom = LinearTaskProvider(api_key="k", review_statuses=["QA Gate"])
    assert custom._map_issue(node(state={"name": "QA Gate", "type": "unstarted"})).status == "review"
    assert custom._map_issue(node(state={"name": "In Review", "type": "started"})).status == "in_progress"


def test_cycle_becomes_sprint():
    t = P._map_issue(node(cycle={"id": "c9", "name": "Cycle 15",
                                 "startsAt": "2026-11-02T00:00:00Z",
                                 "endsAt": "2026-11-15T00:00:00Z"}))
    assert t.sprint_name == "Cycle 15"
    assert t.iteration_path == "linear:cycle:c9"
    assert P._map_issue(node()).sprint_name is None


def test_priority_int_map():
    for value, expected in [(1, "critical"), (2, "high"), (3, "medium"), (4, "low")]:
        assert P._map_issue(node(priority=value)).priority == expected
    # 0 (no priority) and unknown values fall back to medium.
    assert P._map_issue(node(priority=0)).priority == "medium"
    assert P._map_issue(node(priority=None)).priority == "medium"


def test_estimate_becomes_story_points():
    assert P._map_issue(node(estimate=5.0)).story_points == 5
    assert P._map_issue(node(estimate=None)).story_points is None


def test_assignee_identity_is_stable():
    t = P._map_issue(node(assignee={"id": "u-77", "name": "Sarah Chen"}))
    assert t.assignee_name == "Sarah Chen"
    assert t.assignee_external_id == "u-77"


def test_identifier_team_and_tags():
    t = P._map_issue(node(labels={"nodes": [{"name": "payments"}, {"name": "regression"}]}))
    assert t.external_id == "ENG-42"
    assert t.project_name == "ENG"          # identifier prefix = team key
    assert t.work_item_type is None         # Linear has no issue types
    assert t.tags == "payments,regression"
    assert t.area_path is None and t.estimated_hours is None
    assert t.external_state == "Todo"
    assert t.external_changed_at is not None and t.external_changed_at.year == 2026


def test_api_key_required():
    with pytest.raises(ValueError):
        LinearTaskProvider(api_key="")


def test_pick_state():
    states = [
        {"id": "s1", "name": "In Review", "type": "started"},
        {"id": "s2", "name": "Done", "type": "completed"},
    ]
    assert _pick_state(states, "review", DEFAULT_REVIEW_STATUSES)["id"] == "s1"
    assert _pick_state(states, "done", DEFAULT_REVIEW_STATUSES)["id"] == "s2"
    assert _pick_state(states, "backlog", DEFAULT_REVIEW_STATUSES) is None


class FakeLinear(LinearTaskProvider):
    """Records calls, replays canned _data() payloads — no network."""

    def __init__(self, payloads, **kw):
        super().__init__(api_key="k", **kw)
        self.payloads = list(payloads)  # expected data-object responses
        self.queries = []               # (query-first-word, variables)

    async def _data(self, query, variables):
        import json

        self.queries.append((json.dumps(variables, sort_keys=True), query.split("(", 1)[0]))
        return self.payloads.pop(0)


def test_write_side():
    # -- read-only guard fires before any I/O --
    ro = LinearTaskProvider(api_key="k", read_only=True)
    with pytest.raises(Exception, match="read-only"):
        asyncio.run(ro.create_task(ExternalTaskCreate(title="x")))
    with pytest.raises(Exception, match="read-only"):
        asyncio.run(ro.update_task("ENG-42", ExternalTaskUpdate(status="done")))

    # -- create: team from configured key, priority reversed, state resolved --
    p = FakeLinear([
        {"team": {"id": "team-1", "key": "ENG", "name": "Engineering"}},
        {"workflowStates": {"nodes": [
            {"id": "s2", "name": "Done", "type": "completed"},
        ]}},
        {"issueCreate": {"success": True, "issue": node(
            identifier="ENG-99", id="uuid-99",
            state={"name": "Done", "type": "completed"})}},
    ], team_key="ENG")
    created = asyncio.run(p.create_task(ExternalTaskCreate(
        title="Fix checkout", description="Line one", priority="critical",
        status="done", acceptance_criteria="- works")))
    assert created.external_id == "ENG-99"
    assert created.status == "done"
    input_sent = json.loads(p.queries[2][0])["input"]
    assert input_sent["teamId"] == "team-1"
    assert input_sent["priority"] == 1                 # critical -> Urgent
    assert input_sent["stateId"] == "s2"
    assert input_sent["description"] == "Line one\n\n## Acceptance criteria\n- works"

    # -- create without team_key resolves the team from the first issue --
    p = FakeLinear([
        {"issues": {"pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [node()]}},
        {"issueCreate": {"success": True, "issue": node()}},
    ])
    asyncio.run(p.create_task(ExternalTaskCreate(title="x")))
    assert '"teamId": "team-1"' in p.queries[1][0]

    # -- create that lands in backlog/todo asks for no state at all --
    p = FakeLinear([
        {"team": {"id": "team-1", "key": "ENG", "name": "Engineering"}},
        {"issueCreate": {"success": True, "issue": node()}},
    ], team_key="ENG")
    asyncio.run(p.create_task(ExternalTaskCreate(title="x", status="todo")))
    assert "stateId" not in p.queries[1][0]

    # -- update: identifier -> uuid, partial input, final state from reply --
    p = FakeLinear([
        {"issues": {"nodes": [node()]}},
        {"workflowStates": {"nodes": [{"id": "s2", "name": "Done", "type": "completed"}]}},
        {"issueUpdate": {"success": True, "issue": node(
            state={"name": "Done", "type": "completed"}, priority=1)}},
    ])
    updated = asyncio.run(p.update_task(
        "ENG-42", ExternalTaskUpdate(status="done", priority="critical")))
    assert updated.status == "done"
    variables = json.loads(p.queries[2][0])
    assert variables == {"id": "uuid-42", "input": {"priority": 1, "stateId": "s2"}}

    # -- status-only no-op sends nothing --
    p = FakeLinear([{"issues": {"nodes": [node()]}}])
    result = asyncio.run(p.update_task("ENG-42", ExternalTaskUpdate(status="todo")))
    assert result.status == "todo" and len(p.queries) == 1

    # -- unknown issue is loud --
    p = FakeLinear([{"issues": {"nodes": []}}])
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(p.update_task("ENG-404", ExternalTaskUpdate(title="x")))

    # -- GraphQL error surfaces as ValueError --
    class ErrLinear(FakeLinear):
        async def _data(self, query, variables):
            from app.integrations.linear_task_provider import _ISSUE_QUERY
            if query is _ISSUE_QUERY:
                raise ValueError("Linear rejected query: bad filter")
            return await super()._data(query, variables)

    p2 = ErrLinear([{"issues": {"nodes": [node()]}}])
    with pytest.raises(ValueError, match="rejected"):
        asyncio.run(p2.get_task("ENG-42"))


def test_assignee_lookup_prefers_exact_active_user():
    p = FakeLinear([
        {"issues": {"nodes": [node()]}},
        {"users": {"nodes": [
            {"id": "u-1", "name": "Sarah Chen", "active": False},
            {"id": "u-77", "name": "Sarah Chen", "active": True},
            {"id": "u-2", "name": "Sarah Chenoweth", "active": True},
        ]}},
        {"issueUpdate": {"success": True, "issue": node()}},
    ])
    asyncio.run(p.update_task("ENG-42", ExternalTaskUpdate(assignee_name="Sarah Chen")))
    assert '"assigneeId": "u-77"' in p.queries[2][0]

    p = FakeLinear([
        {"issues": {"nodes": [node()]}},
        {"users": {"nodes": []}},
    ])
    with pytest.raises(ValueError, match="no active Linear user"):
        asyncio.run(p.update_task("ENG-42", ExternalTaskUpdate(assignee_name="Nobody")))


def test_list_tasks_pagination():
    p1 = {"pageInfo": {"hasNextPage": True, "endCursor": "c1"}, "nodes": [node()]}
    p2 = {"pageInfo": {"hasNextPage": False, "endCursor": None},
          "nodes": [node(identifier="ENG-43")]}
    # page 1
    p = FakeLinear([{"issues": p1}])
    page = asyncio.run(p.list_tasks())
    assert page.has_more and page.total == 1 and page.items[0].external_id == "ENG-42"
    assert '"after": null' in p.queries[0][0]
    # page 2 walks the cursor
    p = FakeLinear([{"issues": p1}, {"issues": p2}])
    page = asyncio.run(p.list_tasks(page=2))
    assert not page.has_more and page.items[0].external_id == "ENG-43"
    assert page.total == 51  # start-of-page + len, per-page truth
    # page past the end is empty, no extra request
    p = FakeLinear([{"issues": p2}])
    page = asyncio.run(p.list_tasks(page=2))
    assert page.items == [] and not page.has_more


def test_list_sprints_from_team_key():
    import datetime as dt

    p = FakeLinear([
        {"team": {"id": "team-1", "key": "ENG", "name": "Engineering"}},
        {"cycles": {"nodes": [{"id": "c9", "name": "Cycle 15",
                               "startsAt": "2026-11-02T00:00:00Z",
                               "endsAt": "2026-11-15T00:00:00Z"}]}},
    ], team_key="ENG")
    sprints = asyncio.run(p.list_sprints())
    assert len(sprints) == 1
    assert sprints[0].name == "Cycle 15"
    assert sprints[0].path == "linear:cycle:c9"
    assert sprints[0].start_date == dt.date(2026, 11, 2)
    assert sprints[0].end_date == dt.date(2026, 11, 15)
    # unresolvable team -> no sprints, no crash
    p = FakeLinear([{"team": None}], team_key="NOPE")
    assert asyncio.run(p.list_sprints()) == []
