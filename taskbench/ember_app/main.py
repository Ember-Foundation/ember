"""Ember task manager — PostgreSQL (schema: ember)."""
import sys
import os
sys.path.insert(0, "/home/ismail/ember")

import asyncpg
from ember import Ember, Request, JSONResponse, Response
from ember.constants import Events

DB_DSN = "postgresql://postgres:postgres@localhost:5333/salesbird"
app = Ember()

_pool: asyncpg.Pool | None = None

# SQL fragment: serialize one task row to JSON inside PostgreSQL.
# `to_jsonb(t)` is a single C-level conversion; the per-field
# json_build_object form allocated 7 strings and ran 7 type casts per row.
# Field names come from the table schema; UUID → text and timestamptz →
# ISO 8601 conversion happens once per row inside PG.
# Used in SELECT contexts that alias the source table/subquery as `t`.
_TASK_JSON = "to_jsonb(t)"


@app.hook(Events.BEFORE_SERVER_START)
async def on_start(components) -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=DB_DSN,
        min_size=20,
        max_size=100,
        statement_cache_size=512,
        max_inactive_connection_lifetime=300.0,
        command_timeout=5.0,
        server_settings={
            "search_path":         "ember",
            "jit":                 "off",      # JIT adds startup cost for sub-ms queries
            "synchronous_commit":  "off",      # bench-only — commit before WAL fsync
        },
    )
    # Prime every pool connection: open the TCP+startup handshake now so the
    # bench's ramp-up phase doesn't show artificially low throughput while
    # asyncpg fills the pool lazily.
    conns: list[asyncpg.Connection] = []
    try:
        for _ in range(_pool.get_min_size()):
            conns.append(await _pool.acquire())
        for c in conns:
            await c.execute("SELECT 1")
    finally:
        for c in conns:
            await _pool.release(c)


@app.hook(Events.BEFORE_SERVER_STOP)
async def on_stop(components) -> None:
    if _pool:
        await _pool.close()


def _json_response(json_text: str, status: int = 200) -> Response:
    """Wrap a PG-produced JSON string as a response — zero Python dict creation."""
    return Response(
        json_text.encode(),
        status_code=status,
        content_type=b'application/json; charset=utf-8',
    )


@app.get("/health")
async def health(request: Request) -> JSONResponse:
    count = await _pool.fetchval("SELECT COUNT(*) FROM tasks")
    return JSONResponse({"status": "ok", "tasks": count})


@app.get("/tasks")
async def list_tasks(request: Request) -> Response:
    page  = int(request.get_arg("page",  "1"))
    limit = int(request.get_arg("limit", "20"))
    offset = (page - 1) * limit
    # Single query: tasks JSON array + total count via window function
    row = await _pool.fetchrow(
        f"""
        SELECT
            COALESCE(json_agg({_TASK_JSON}), '[]'::json)::text  AS tasks,
            (SELECT COUNT(*) FROM tasks)::int                    AS total
        FROM (SELECT * FROM tasks ORDER BY created_at DESC LIMIT $1 OFFSET $2) t
        """,
        limit, offset,
    )
    body = f'{{"tasks":{row["tasks"]},"total":{row["total"]},"page":{page},"limit":{limit}}}'
    return _json_response(body)


@app.get("/tasks/all")
async def list_all(request: Request) -> Response:
    row = await _pool.fetchrow(
        f"""
        SELECT
            COALESCE(json_agg({_TASK_JSON}), '[]'::json)::text AS tasks,
            COUNT(*)::int                                        AS total
        FROM tasks t
        """,
    )
    body = f'{{"tasks":{row["tasks"]},"total":{row["total"]}}}'
    return _json_response(body)


@app.get("/tasks/{task_id}")
async def get_task(request: Request, task_id: str) -> Response:
    json_text = await _pool.fetchval(
        f"SELECT {_TASK_JSON}::text FROM tasks t WHERE id = $1",
        task_id,
    )
    if json_text is None:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return _json_response(json_text)


@app.post("/tasks")
async def create_task(request: Request) -> Response:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    # RETURNING references the table-row composite directly (no `t` alias is
    # bound in the RETURNING clause for a plain INSERT, so we use `tasks`).
    json_text = await _pool.fetchval(
        """
        INSERT INTO tasks (title, description, completed, priority)
        VALUES ($1, $2, $3, $4)
        RETURNING to_jsonb(tasks)::text
        """,
        body.get("title", "Untitled"),
        body.get("description", ""),
        bool(body.get("completed", False)),
        body.get("priority", "medium"),
    )
    return _json_response(json_text, status=201)


@app.patch("/tasks/{task_id}")
async def update_task(request: Request, task_id: str) -> Response:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    json_text = await _pool.fetchval(
        """
        UPDATE tasks SET
            title       = COALESCE($2, title),
            description = COALESCE($3, description),
            completed   = COALESCE($4, completed),
            priority    = COALESCE($5, priority),
            updated_at  = NOW()
        WHERE id = $1
        RETURNING to_jsonb(tasks)::text
        """,
        task_id,
        body.get("title"),
        body.get("description"),
        body.get("completed"),
        body.get("priority"),
    )
    if json_text is None:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return _json_response(json_text)


@app.delete("/tasks/{task_id}")
async def delete_task(request: Request, task_id: str) -> Response:
    result = await _pool.execute("DELETE FROM tasks WHERE id = $1", task_id)
    if result == "DELETE 0":
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return Response(b"", status_code=204)


@app.handle(Exception)
async def handle_error(exc: Exception) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9002, workers=1, debug=False, startup_message=True)
