"""FastAPI task manager — PostgreSQL (schema: ember)."""
import uvicorn
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

DB_DSN = "postgresql://postgres:postgres@localhost:5333/salesbird"
POOL: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global POOL
    POOL = await asyncpg.create_pool(
        dsn=DB_DSN,
        min_size=4, max_size=20,
        server_settings={"search_path": "ember"},
    )
    yield
    await POOL.close()


app = FastAPI(title="TaskManager FastAPI", docs_url=None, redoc_url=None, lifespan=lifespan)


class TaskIn(BaseModel):
    title: str
    description: str = ""
    completed: bool = False
    priority: str = "medium"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None


def row_to_dict(r) -> dict:
    return {
        "id": str(r["id"]),
        "title": r["title"],
        "description": r["description"],
        "completed": r["completed"],
        "priority": r["priority"],
        "created_at": r["created_at"].isoformat(),
        "updated_at": r["updated_at"].isoformat(),
    }


@app.get("/health")
async def health():
    count = await POOL.fetchval("SELECT COUNT(*) FROM tasks")
    return {"status": "ok", "tasks": count}


@app.get("/tasks")
async def list_tasks(page: int = 1, limit: int = 20):
    offset = (page - 1) * limit
    rows = await POOL.fetch(
        "SELECT * FROM tasks ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        limit, offset,
    )
    total = await POOL.fetchval("SELECT COUNT(*) FROM tasks")
    return {"tasks": [row_to_dict(r) for r in rows], "total": total, "page": page, "limit": limit}


@app.get("/tasks/all")
async def list_all():
    rows = await POOL.fetch("SELECT * FROM tasks ORDER BY created_at DESC")
    return {"tasks": [row_to_dict(r) for r in rows], "total": len(rows)}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    row = await POOL.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
    if not row:
        raise HTTPException(404, "Task not found")
    return row_to_dict(row)


@app.post("/tasks", status_code=201)
async def create_task(body: TaskIn):
    row = await POOL.fetchrow(
        "INSERT INTO tasks (title,description,completed,priority) VALUES($1,$2,$3,$4) RETURNING *",
        body.title, body.description, body.completed, body.priority,
    )
    return row_to_dict(row)


@app.patch("/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate):
    row = await POOL.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
    if not row:
        raise HTTPException(404, "Task not found")
    updated = await POOL.fetchrow(
        """UPDATE tasks SET
             title       = COALESCE($2, title),
             description = COALESCE($3, description),
             completed   = COALESCE($4, completed),
             priority    = COALESCE($5, priority),
             updated_at  = NOW()
           WHERE id = $1 RETURNING *""",
        task_id, body.title, body.description, body.completed, body.priority,
    )
    return row_to_dict(updated)


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str):
    result = await POOL.execute("DELETE FROM tasks WHERE id = $1", task_id)
    if result == "DELETE 0":
        raise HTTPException(404, "Task not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9001, log_level="warning", loop="uvloop")
