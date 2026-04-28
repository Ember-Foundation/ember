# 5 — Blueprints

Blueprints let you split routes across multiple files and mount them at a URL prefix. They work exactly like the main `app` — same decorators, same hooks, same exception handlers.

---

## Basic Blueprint

```python
# routes/tasks.py
from ember import Blueprint, Request, JSONResponse

tasks_bp = Blueprint()
_db: dict = {}

@tasks_bp.get("/")
async def list_tasks(request: Request) -> JSONResponse:
    return JSONResponse({"tasks": list(_db.values())})

@tasks_bp.post("/")
async def create_task(request: Request) -> JSONResponse:
    import uuid
    data = await request.json()
    task_id = str(uuid.uuid4())
    _db[task_id] = {"id": task_id, **data}
    return JSONResponse(_db[task_id], status_code=201)

@tasks_bp.get("/{task_id:str}")
async def get_task(request: Request, task_id: str) -> JSONResponse:
    task = _db.get(task_id)
    if not task:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(task)
```

Mount it in the main app:

```python
# main.py
from ember import Ember
from routes.tasks import tasks_bp

app = Ember()
app.add_blueprint(tasks_bp, prefixes={"*": "/tasks"})

if __name__ == "__main__":
    app.run(port=8000)
```

Routes become:

```
GET    /tasks/
POST   /tasks/
GET    /tasks/{task_id}
```

---

## Multiple Blueprints

```python
# main.py
from ember import Ember
from routes.tasks  import tasks_bp
from routes.users  import users_bp
from routes.admin  import admin_bp

app = Ember()
app.add_blueprint(tasks_bp, prefixes={"*": "/tasks"})
app.add_blueprint(users_bp, prefixes={"*": "/users"})
app.add_blueprint(admin_bp, prefixes={"*": "/admin"})

if __name__ == "__main__":
    app.run(port=8000)
```

---

## Blueprint-Level Defaults

Apply default limits and middleware to all routes in a blueprint:

```python
from ember import Blueprint, RouteLimits

api_bp = Blueprint(
    limits=RouteLimits(max_body_size=1 * 1024 * 1024),  # 1 MB for all routes
)

@api_bp.post("/upload")
async def upload(request):
    # Inherits 1 MB limit from blueprint
    raw = await request.body()
    return {"size": len(raw)}

@api_bp.post("/big-upload", limits=RouteLimits(max_body_size=50 * 1024 * 1024))
async def big_upload(request):
    # Per-route override: 50 MB
    raw = await request.body()
    return {"size": len(raw)}
```

---

## Blueprint Hooks

Hooks on a blueprint run on all requests routed to that blueprint:

```python
from ember import Blueprint, Events

admin_bp = Blueprint()

@admin_bp.hook(Events.BEFORE_ENDPOINT)
async def require_admin(request, response):
    from ember import JSONResponse
    user = request.context.get("auth", {})
    if "admin" not in user.get("roles", []):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None

@admin_bp.get("/users")
async def list_users(request):
    return {"users": []}
```

---

## Nested Blueprints

Blueprints can contain other blueprints:

```python
v1 = Blueprint()
v1.add_blueprint(tasks_bp, prefixes={"*": "/tasks"})
v1.add_blueprint(users_bp, prefixes={"*": "/users"})

app.add_blueprint(v1, prefixes={"*": "/api/v1"})
# → /api/v1/tasks, /api/v1/users
```

---

## Project Layout With Blueprints

```
myapp/
  main.py
  routes/
    __init__.py
    tasks.py      # tasks_bp
    users.py      # users_bp
    admin.py      # admin_bp
  services/
    tasks.py      # business logic
    users.py
  models/
    task.py
    user.py
```

```python
# main.py
from ember import Ember
from routes.tasks import tasks_bp
from routes.users import users_bp
from routes.admin import admin_bp
from ember import CORSMiddleware, BearerAuthMiddleware, Events

app = Ember()
app.add_middleware(CORSMiddleware(allow_origins=["*"]))
app.add_middleware(BearerAuthMiddleware(verify_fn=lambda t: bool(t), exclude_paths=["/"]))
app.add_blueprint(tasks_bp, prefixes={"*": "/tasks"})
app.add_blueprint(users_bp, prefixes={"*": "/users"})
app.add_blueprint(admin_bp, prefixes={"*": "/admin"})

@app.hook(Events.BEFORE_SERVER_START)
async def startup(components):
    print("Server starting...")

if __name__ == "__main__":
    app.run(workers=4)
```

**Next:** [Caching →](./06-caching)
