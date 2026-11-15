# Todo API

A small FastAPI service exposing an in-memory Todo CRUD API. It exists as a
clean, readable starting point for new features.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Interactive docs at http://localhost:8000/docs.

## Endpoints

| Method | Path          | Description            |
| ------ | ------------- | ---------------------- |
| GET    | `/health`     | Liveness check         |
| GET    | `/todos`      | List all todos         |
| POST   | `/todos`      | Create a todo          |
| GET    | `/todos/{id}` | Fetch a todo by id     |
| PATCH  | `/todos/{id}` | Partially update a todo|
| DELETE | `/todos/{id}` | Delete a todo          |

## Test

```bash
pytest
```
