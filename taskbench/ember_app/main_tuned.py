"""Ember task manager — high single-thread concurrency via framework primitives.

Compare with main.py: same routes, same SQL, but reads use Ember's TTLCache
(TTL + bounded LRU + single-flight) and the COUNT(*) is replaced by reltuples.
No user-land cache or singleflight bookkeeping — it's all in the framework now.
"""
import sys
sys.path.insert(0, "/home/ismail/ember")

import asyncpg
from ember import Ember, Request, JSONResponse, Response
from ember.cache import TTLCache
from ember.constants import Events

DB_DSN = "postgresql://postgres:postgres@localhost:5333/salesbird"
app = Ember()

_pool: asyncpg.Pool | None = None
_TASK_JSON = "to_jsonb(t)"

# One TTL+single-flight cache per read route. 1s TTL is invisible to humans
# but collapses thundering-herd traffic into a single PG roundtrip per second.
list_cache = TTLCache(ttl=1.0, max_entries=512)
all_cache  = TTLCache(ttl=1.0, max_entries=4)
item_cache = TTLCache(ttl=1.0, max_entries=4096)


@app.hook(Events.BEFORE_SERVER_START)
async def on_start(components) -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=DB_DSN,
        min_size=200, max_size=200,
        statement_cache_size=512,
        max_inactive_connection_lifetime=300.0,
        command_timeout=5.0,
        server_settings={
            "search_path":         "ember",
            "jit":                 "off",
            "synchronous_commit":  "off",
        },
    )
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
    return Response(
        json_text.encode() if isinstance(json_text, str) else json_text,
        status_code=status,
        content_type=b'application/json; charset=utf-8',
    )


def _invalidate_lists(task_id: str | None = None) -> None:
    list_cache.invalidate()
    all_cache.invalidate()
    if task_id is not None:
        item_cache.invalidate_prefix(f"/tasks/{task_id}")


@app.get("/health")
async def health(request: Request) -> JSONResponse:
    count = await _pool.fetchval(
        "SELECT reltuples::bigint FROM pg_class WHERE relname='tasks'"
    )
    return JSONResponse({"status": "ok", "tasks": count})


@app.get("/tasks", cache=list_cache)
async def list_tasks(request: Request) -> Response:
    page  = int(request.get_arg("page",  "1"))
    limit = int(request.get_arg("limit", "20"))
    offset = (page - 1) * limit
    row = await _pool.fetchrow(
        f"""
        SELECT
            COALESCE(json_agg({_TASK_JSON}), '[]'::json)::text AS tasks,
            (SELECT reltuples::bigint FROM pg_class WHERE relname='tasks') AS total
        FROM (SELECT * FROM tasks ORDER BY created_at DESC LIMIT $1 OFFSET $2) t
        """,
        limit, offset,
    )
    body = f'{{"tasks":{row["tasks"]},"total":{row["total"]},"page":{page},"limit":{limit}}}'
    return _json_response(body)


@app.get("/tasks/all", cache=all_cache)
async def list_all(request: Request) -> Response:
    row = await _pool.fetchrow(
        f"""
        SELECT
            COALESCE(json_agg({_TASK_JSON}), '[]'::json)::text AS tasks,
            (SELECT reltuples::bigint FROM pg_class WHERE relname='tasks') AS total
        FROM tasks t
        """,
    )
    body = f'{{"tasks":{row["tasks"]},"total":{row["total"]}}}'
    return _json_response(body)


@app.get("/tasks/{task_id}", cache=item_cache)
async def get_task(request: Request, task_id: str) -> Response:
    json_text = await _pool.fetchval(
        f"SELECT {_TASK_JSON}::text FROM tasks t WHERE id = $1", task_id,
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
    _invalidate_lists()
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
    _invalidate_lists(task_id)
    return _json_response(json_text)


@app.delete("/tasks/{task_id}")
async def delete_task(request: Request, task_id: str) -> Response:
    result = await _pool.execute("DELETE FROM tasks WHERE id = $1", task_id)
    if result == "DELETE 0":
        return JSONResponse({"error": "Task not found"}, status_code=404)
    _invalidate_lists(task_id)
    return Response(b"", status_code=204)


@app.handle(Exception)
async def handle_error(exc: Exception) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9002, workers=1, debug=False, startup_message=True)
