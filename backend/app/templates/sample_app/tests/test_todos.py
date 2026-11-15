"""CRUD tests for the Todo API."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_store():
    store.clear()
    yield


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_todo():
    resp = client.post("/todos", json={"title": "Buy milk", "description": "2 litres"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == 1
    assert body["title"] == "Buy milk"
    assert body["description"] == "2 litres"
    assert body["completed"] is False
    assert body["created_at"]


def test_create_todo_requires_title():
    resp = client.post("/todos", json={"description": "no title"})
    assert resp.status_code == 422


def test_list_todos():
    client.post("/todos", json={"title": "First"})
    client.post("/todos", json={"title": "Second"})
    resp = client.get("/todos")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert titles == ["First", "Second"]


def test_get_todo():
    created = client.post("/todos", json={"title": "Read a book"}).json()
    resp = client.get(f"/todos/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Read a book"


def test_get_missing_todo_returns_404():
    resp = client.get("/todos/999")
    assert resp.status_code == 404


def test_update_todo():
    created = client.post("/todos", json={"title": "Draft email"}).json()
    resp = client.patch(f"/todos/{created['id']}", json={"completed": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed"] is True
    assert body["title"] == "Draft email"  # untouched fields are preserved


def test_update_missing_todo_returns_404():
    resp = client.patch("/todos/999", json={"completed": True})
    assert resp.status_code == 404


def test_delete_todo():
    created = client.post("/todos", json={"title": "Take out trash"}).json()
    resp = client.delete(f"/todos/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/todos/{created['id']}").status_code == 404


def test_delete_missing_todo_returns_404():
    resp = client.delete("/todos/999")
    assert resp.status_code == 404
