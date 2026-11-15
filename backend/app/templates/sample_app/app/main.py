"""Todo API application entry point."""

from fastapi import FastAPI

from app.routes import router

app = FastAPI(title="Todo API", version="0.1.0")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
