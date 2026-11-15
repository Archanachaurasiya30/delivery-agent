"""In-memory todo store.

State lives in a plain dict and is lost on restart — this app is a demo
starting point, not a production service.
"""

from datetime import datetime, timezone

from app.models import Todo, TodoCreate, TodoUpdate


class TodoStore:
    def __init__(self) -> None:
        self._todos: dict[int, Todo] = {}
        self._next_id = 1

    def create(self, data: TodoCreate) -> Todo:
        todo = Todo(
            id=self._next_id,
            title=data.title,
            description=data.description,
            completed=False,
            created_at=datetime.now(timezone.utc),
        )
        self._todos[todo.id] = todo
        self._next_id += 1
        return todo

    def get(self, todo_id: int) -> Todo | None:
        return self._todos.get(todo_id)

    def list(self) -> list[Todo]:
        return list(self._todos.values())

    def update(self, todo_id: int, data: TodoUpdate) -> Todo | None:
        todo = self._todos.get(todo_id)
        if todo is None:
            return None
        updated = todo.model_copy(update=data.model_dump(exclude_unset=True))
        self._todos[todo_id] = updated
        return updated

    def delete(self, todo_id: int) -> bool:
        return self._todos.pop(todo_id, None) is not None

    def clear(self) -> None:
        """Reset the store (used by tests)."""
        self._todos.clear()
        self._next_id = 1


# Module-level singleton shared by the routes.
store = TodoStore()
