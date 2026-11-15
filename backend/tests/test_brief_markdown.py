"""Pure tests for the markdown brief export (issue #15).

Same philosophy as test_demo_mode / test_passcode_gate: no network, no DB.
``to_markdown`` runs on an in-memory Brief; the endpoint is exercised through
TestClient with ``get_db`` overridden by a stub session — the same query the
route issues, answered without Postgres.
"""

from datetime import date

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.brief import Brief
from app.services.brief_service import BriefService

def make_brief() -> Brief:
    return Brief(
        brief_date=date(2026, 11, 15),
        headline="Sprint 2404 on track",
        content={
            "shipped": ["Payment retry job"],
            "ai_delivered": ["Refactored checkout tests"],
            "risks": [],
            "needs_decision": ["Approve the Storefront rollout"],
            "numbers": {"confidence": "82%"},
            "narrative": "Steady day.",
        },
    )


def test_to_markdown_shape():
    md = BriefService.to_markdown(make_brief())
    assert md.startswith("# ")
    assert "2026-11-15" in md
    assert "## Shipped" in md and "- Payment retry job" in md
    assert "## Needs your decision" in md
    assert "## Numbers" in md and "- confidence: 82%" in md
    assert "Risks" not in md  # empty sections are skipped


def test_to_markdown_survives_empty_content():
    brief = Brief(brief_date=date(2026, 11, 15), headline="", content={})
    md = BriefService.to_markdown(brief)
    assert md == f"# Morning brief — {date(2026, 11, 15)}"


class _FakeResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeDB:
    def __init__(self, brief):
        self._brief = brief

    async def execute(self, *_args, **_kw):
        return _FakeResult(self._brief)


def _client(brief) -> TestClient:
    # Override must stay registered for the client's lifetime — popped by the
    # caller's finally, mirroring the settings toggles in test_passcode_gate.
    app.dependency_overrides[get_db] = lambda: _FakeDB(brief)
    return TestClient(app)


def test_endpoint_returns_markdown():
    brief = make_brief()
    try:
        res = _client(brief).get("/api/v1/briefs/whatever/markdown")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    assert res.text.startswith("# ")


def test_endpoint_404_for_unknown_id():
    try:
        res = _client(None).get("/api/v1/briefs/nope/markdown")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert res.status_code == 404
