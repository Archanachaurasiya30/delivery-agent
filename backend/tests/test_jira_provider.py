"""Pure mapping tests for the Jira provider.

Same philosophy as test_github_provider: no network, no fixtures — feed
crafted REST v3 issue JSON into the mapper and assert the contract the import
layer depends on. The status mapping (statusCategory + review-status
override) is the public interface to anyone pointing the app at a Jira site;
these tests are its spec.
"""

import asyncio

import pytest

from app.integrations.jira_task_provider import JiraTaskProvider
from app.integrations.task_provider import ExternalTaskCreate

P = JiraTaskProvider(url="https://acme.atlassian.net", email="a@b.c", api_token="t")


def issue(**over):
    base = {
        "id": "10042",
        "key": "NW-42",
        "fields": {
            "summary": "Fix checkout",
            "description": None,
            "status": {"name": "To Do", "statusCategory": {"key": "new"}},
            "assignee": None,
            "priority": {"name": "Medium"},
            "issuetype": {"name": "Task"},
            "fixVersions": [],
            "labels": [],
            "updated": "2026-11-15T09:00:00.000+0000",
        },
    }
    base["fields"].update(over.pop("fields", {}))
    base.update(over)
    return base


def status(name, category):
    return {"name": name, "statusCategory": {"key": category}}


def test_status_categories():
    assert P._map_issue(issue(fields={"status": status("To Do", "new")})).status == "backlog"
    assert P._map_issue(issue(fields={"status": status("In Dev", "indeterminate")})).status == "in_progress"
    assert P._map_issue(issue(fields={"status": status("Closed", "done")})).status == "done"


def test_review_status_name_overrides_category():
    # "In Review" boards as review even though its category is indeterminate.
    t = P._map_issue(issue(fields={"status": status("In Review", "indeterminate")}))
    assert t.status == "review"
    # Custom list replaces the default, not extends it.
    custom = JiraTaskProvider(url="https://x.atlassian.net", email="a", api_token="t",
                              review_statuses=["QA Gate"])
    assert custom._map_issue(issue(fields={"status": status("QA Gate", "new")})).status == "review"
    assert custom._map_issue(issue(fields={"status": status("In Review", "indeterminate")})).status == "in_progress"


def test_fixversion_becomes_sprint():
    t = P._map_issue(issue(fields={"fixVersions": [{"id": "5", "name": "Sprint 15",
                                                    "releaseDate": "2026-11-30"}]}))
    assert t.sprint_name == "Sprint 15"
    assert t.iteration_path == "jira:NW#5"
    assert P._map_issue(issue()).sprint_name is None


def test_priority_name_map():
    for name, expected in [("Highest", "critical"), ("High", "critical"),
                           ("Medium", "medium"), ("Low", "low"), ("Lowest", "low")]:
        assert P._map_issue(issue(fields={"priority": {"name": name}})).priority == expected
    # Unknown or absent priority falls back to medium.
    assert P._map_issue(issue(fields={"priority": {"name": "Trivial"}})).priority == "medium"
    assert P._map_issue(issue(fields={"priority": None})).priority == "medium"


def test_description_doc_json_is_flattened():
    doc = {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Fix the pay flow."}]},
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "visa"}]},
                ]},
                {"type": "listItem", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "amex"}]},
                ]},
            ]},
        ],
    }
    t = P._map_issue(issue(fields={"description": doc}))
    assert t.description == "Fix the pay flow.\nvisa\namex"
    assert P._map_issue(issue()).description is None


def test_assignee_identity_is_stable():
    t = P._map_issue(issue(fields={"assignee": {"accountId": "5b10a2",
                                                "displayName": "Sarah Chen"}}))
    assert t.assignee_name == "Sarah Chen"
    assert t.assignee_external_id == "5b10a2"


def test_key_and_project_and_type():
    t = P._map_issue(issue())
    assert t.external_id == "NW-42"
    assert t.project_name == "NW"           # key prefix
    assert t.work_item_type == "Task"       # issuetype passes through as-is
    assert P._map_issue(issue(fields={"issuetype": {"name": "Bug"}})).work_item_type == "Bug"
    assert t.area_path is None and t.story_points is None and t.estimated_hours is None
    assert t.external_state == "To Do"
    assert t.external_changed_at is not None and t.external_changed_at.year == 2026


def test_labels_join_to_tags():
    t = P._map_issue(issue(fields={"labels": ["payments", "regression"]}))
    assert t.tags == "payments,regression"


def test_url_must_be_absolute():
    with pytest.raises(ValueError):
        JiraTaskProvider(url="acme.atlassian.net", email="a", api_token="t")


def test_write_side_not_implemented_yet():
    with pytest.raises(NotImplementedError):
        asyncio.run(P.create_task(ExternalTaskCreate(title="x")))
    from app.integrations.task_provider import ExternalTaskUpdate
    with pytest.raises(NotImplementedError):
        asyncio.run(P.update_task("NW-42", ExternalTaskUpdate(status="done")))
