"""Pure tests for release-notes drafting (issue #14).

Same philosophy as test_github_provider / test_passcode_gate: no network, no
DB. The LLM helper is monkeypatched and the session is a fake that replays
canned query results in call order; TestClient drives the real router so the
201/409/404 contract of POST /sprints/{id}/release-notes is what is asserted.
"""

from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient

import app.services.sprint_service as sprint_service_module
from app.database import get_db
from app.integrations.demo_llm import demo_completion
from app.main import app
from app.models.proposal import Proposal
from app.models.sprint import Sprint
from app.models.task import Task

SPRINT_ID = "11111111-1111-1111-1111-111111111111"
MARKDOWN = "## Sprint 2403\n\n### Features\n- Order status (#4105)\n"


def make_sprint():
    return Sprint(
        id=SPRINT_ID,
        name="Sprint 2403",
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 15),
        status="completed",
    )


def done_tasks():
    def t(title, area, ext, wtype):
        return Task(
            id=str(uuid4()),
            title=title,
            project_name=area,
            external_id=ext,
            work_item_type=wtype,
            status="done",
        )

    return [
        t("Order status page", "Storefront", "4105", "User Story"),
        t("Group invites on iOS", "Storefront", "4112", "User Story"),
        t("Fix loyalty DAL batch", "Loyalty & Infra", "4109", "Bug"),
    ]


class FakeResult:
    """Just enough of a SQLAlchemy result for the service's query shapes."""

    def __init__(self, rows):
        self._rows = rows if isinstance(rows, list) else ([] if rows is None else [rows])

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class FakeDB:
    """AsyncSession stand-in: pops one canned result per execute(), in order."""

    def __init__(self, results):
        self._results = list(results)
        self.added = []

    async def execute(self, query):
        return self._results.pop(0)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        # Stand in for the real INSERT: apply the python-side id default.
        for o in self.added:
            if getattr(o, "id", None) is None:
                o.id = str(uuid4())

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def rollback(self):
        pass

    async def close(self):
        pass


class FakeLLM:
    def __init__(self):
        self.prompts = []

    async def __call__(self, messages, **kwargs):
        self.prompts.append("\n".join(str(m.get("content")) for m in messages))
        return MARKDOWN


async def _boom(messages, **kwargs):
    raise AssertionError("LLM must not be called on this path")


def override(db):
    async def _override():
        yield db

    return _override


def test_post_creates_pending_release_notes_proposal(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(sprint_service_module, "groq_chat", llm)
    db = FakeDB(
        [
            FakeResult(make_sprint()),  # get_sprint
            FakeResult([]),  # no pending release_notes proposal
            FakeResult(make_sprint()),  # get_sprint_tasks existence check
            FakeResult(done_tasks()),  # done tasks
        ]
    )
    app.dependency_overrides[get_db] = override(db)
    try:
        r = TestClient(app).post(f"/api/v1/sprints/{SPRINT_ID}/release-notes")
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["type"] == "release_notes"
        assert body["state"] == "pending_review"
        assert body["created_by_agent"] == "release-notes"
        assert body["id"] and body["id"] != "None"
        assert body["content"]["sprint_id"] == SPRINT_ID
        assert body["content"]["markdown"] == MARKDOWN
        # The prompt carried the real done items (ids + titles), nothing else.
        assert "Order status page" in llm.prompts[0] and "#4105" in llm.prompts[0]
        assert "#4109" in llm.prompts[0]
        assert len(db.added) == 1
    finally:
        app.dependency_overrides.clear()


def test_second_draft_while_pending_is_409(monkeypatch):
    monkeypatch.setattr(sprint_service_module, "groq_chat", _boom)
    existing = Proposal(
        type="release_notes",
        state="pending_review",
        content={"sprint_id": SPRINT_ID, "markdown": "earlier draft"},
    )
    db = FakeDB([FakeResult(make_sprint()), FakeResult([existing])])
    app.dependency_overrides[get_db] = override(db)
    try:
        r = TestClient(app).post(f"/api/v1/sprints/{SPRINT_ID}/release-notes")
        assert r.status_code == 409
        assert "pending review" in r.json()["detail"]
        assert not db.added
    finally:
        app.dependency_overrides.clear()


def test_unknown_sprint_is_404(monkeypatch):
    monkeypatch.setattr(sprint_service_module, "groq_chat", _boom)
    db = FakeDB([FakeResult(None)])
    app.dependency_overrides[get_db] = override(db)
    try:
        r = TestClient(app).post(
            f"/api/v1/sprints/{uuid4()}/release-notes"
        )
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_demo_mode_replays_markdown_release_notes():
    out = demo_completion(
        [
            {"role": "system", "content": "You are a technical writer."},
            {
                "role": "user",
                "content": (
                    "Draft release notes for Sprint 2403 (ended 2026-11-15). "
                    "Done items (facts): [{\"item\": \"#4105\"}]"
                ),
            },
        ]
    )
    assert out.lstrip().startswith("## Sprint 2403")
    assert "### Features" in out and "#4105" in out
    assert not out.lstrip().startswith("{")  # markdown, never JSON
