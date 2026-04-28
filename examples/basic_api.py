"""Basic Ember API example.

Covers: routes, blueprints, JSON responses, path parameters, middleware.

Run:
    python examples/basic_api.py
"""
import sys
sys.path.insert(0, ".")

from ember import (
    Ember,
    Blueprint,
    Request,
    JSONResponse,
    Response,
    CORSMiddleware,
    APIKeyMiddleware,
    StaticCache,
    Events,
    Hook,
)

app = Ember()

# ── CORS middleware (registered as BEFORE_ENDPOINT hook) ─────────────────────
app.add_middleware(CORSMiddleware(allow_origins=["http://localhost:3000", "*"]))

# ── Static routes ──────────────────────────────────────────────────────────────

@app.get("/")
async def index(request: Request) -> JSONResponse:
    return JSONResponse({"name": "Ember", "version": "0.1.0", "status": "ok"})


@app.get("/health", cache=StaticCache())
async def health() -> JSONResponse:
    # StaticCache: first response is cached; subsequent requests skip this handler
    return JSONResponse({"status": "healthy"})


# ── Path parameters ────────────────────────────────────────────────────────────

@app.get("/users/{user_id:int}")
async def get_user(request: Request, user_id: int) -> JSONResponse:
    return JSONResponse({"user_id": user_id, "name": f"User {user_id}"})


@app.get("/posts/{slug:str}")
async def get_post(request: Request, slug: str) -> JSONResponse:
    return JSONResponse({"slug": slug, "title": slug.replace("-", " ").title()})


# ── Blueprint ──────────────────────────────────────────────────────────────────

admin = Blueprint()


@admin.get("/stats")
async def admin_stats(request: Request) -> JSONResponse:
    return JSONResponse({"active_connections": 0, "requests_total": 0})


@admin.post("/reload")
async def admin_reload(request: Request) -> JSONResponse:
    return JSONResponse({"message": "Configuration reloaded"})


app.add_blueprint(admin, prefixes={"*": "/admin"})


# ── Lifecycle hooks ────────────────────────────────────────────────────────────

@app.hook(Events.BEFORE_SERVER_START)
async def on_startup(components) -> None:
    print("  Server starting up...")


@app.hook(Events.BEFORE_SERVER_STOP)
async def on_shutdown(components) -> None:
    print("  Server shutting down...")


# ── Exception handlers ─────────────────────────────────────────────────────────

@app.handle(404)
async def not_found(exc) -> JSONResponse:
    return JSONResponse({"error": "not_found"}, status_code=404)


@app.handle(500)
async def server_error(exc) -> JSONResponse:
    return JSONResponse({"error": "internal_server_error"}, status_code=500)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, workers=2, debug=True)
