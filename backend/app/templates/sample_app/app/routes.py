"""CRUD routes for todos."""

from fastapi import APIRouter, HTTPException, status

from app.models import Todo, TodoCreate, TodoUpdate
from app.store import store

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("", response_model=list[Todo])
def list_todos() -> list[Todo]:
    return store.list()


@router.post("", response_model=Todo, status_code=status.HTTP_201_CREATED)
def create_todo(data: TodoCreate) -> Todo:
    return store.create(data)


@router.get("/{todo_id}", response_model=Todo)
def get_todo(todo_id: int) -> Todo:
    todo = store.get(todo_id)
    if todo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    return todo


@router.patch("/{todo_id}", response_model=Todo)
def update_todo(todo_id: int, data: TodoUpdate) -> Todo:
    todo = store.update(todo_id, data)
    if todo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    return todo


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int) -> None:
    if not store.delete(todo_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
