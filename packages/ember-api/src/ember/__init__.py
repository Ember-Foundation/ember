"""
Ember — the fastest Python web framework.

Engineered for raw speed and concurrency:
  - llhttp + Cython hot-path compilation
  - io_uring event loop (epoll/kqueue fallback)
  - Multi-process SO_REUSEPORT workers, fork-based supervision
  - TTL + single-flight cache primitives built into the router
  - Native async with uvloop
  - First-class SSE streaming, AI primitives, conversation context, model routing
"""
import importlib as _importlib
import pkgutil as _pkgutil

# Extend the package's __path__ to include `ember/` directories from sibling
# distributions (emberloop, ember-cache). They contribute submodules like
# ember.protocol, ember.eventloop, ember.cache without owning ember/__init__.py.
__path__ = _pkgutil.extend_path(__path__, __name__)

try:
    from .eventloop import install_best_event_loop
    install_best_event_loop()
except Exception:
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass

# ── Eager core: needed by every Ember app ─────────────────────────────────────
from .__version__ import __version__
from .server import Ember
from .application import Blueprint
from .request import Request
from .response import (
    Response,
    JSONResponse,
    StreamingResponse,
    SSEResponse,
    TokenStreamResponse,
    RedirectResponse,
)
from .hooks import Hook
from .constants import Events
from .limits import ServerLimits, RouteLimits, TokenLimits
from .exceptions import (
    RouteNotFound,
    MethodNotAllowed,
    RateLimitExceeded,
    TokenLimitExceeded,
    ModelUnavailable,
)

# ── Lazy: optional namespaces (AI / middleware / cache) ───────────────────────
# Imported on first attribute access via PEP 562 __getattr__. This avoids
# pulling in numpy / redis / memcached clients for HTTP-only apps and trims
# ~2–4 MB off cold-start RSS.
_LAZY: dict[str, str] = {
    # ember.ai
    "ConversationContext": ".ai",
    "Message":             ".ai",
    "MessageRole":         ".ai",
    "PromptTemplate":      ".ai",
    "TemplateVar":         ".ai",
    "ToolRegistry":        ".ai",
    "ToolResult":          ".ai",
    "tool":                ".ai",
    "ModelRouter":         ".ai",
    "ModelSpec":           ".ai",
    "RoutingStrategy":     ".ai",
    "SemanticCache":       ".ai",
    "SSEWriter":           ".ai",
    "sse_stream":          ".ai",
    "TokenBucket":         ".ai",
    "GlobalTokenBucket":   ".ai",
    "RateLimitMiddleware": ".ai",
    # ember.middleware
    "CORSMiddleware":        ".middleware",
    "BearerAuthMiddleware":  ".middleware",
    "APIKeyMiddleware":      ".middleware",
    # ember.cache
    "StaticCache":    ".cache",
    "RedisCache":     ".cache",
    "MemcachedCache": ".cache",
}


def __getattr__(name: str):
    mod_path = _LAZY.get(name)
    if mod_path is None:
        raise AttributeError(f"module 'ember' has no attribute {name!r}")
    mod = _importlib.import_module(mod_path, __name__)
    val = getattr(mod, name)
    globals()[name] = val   # cache for next access
    return val


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY))


__all__ = [
    "__version__",
    "Ember",
    "Blueprint",
    "Request",
    "Response",
    "JSONResponse",
    "StreamingResponse",
    "SSEResponse",
    "TokenStreamResponse",
    "RedirectResponse",
    "Hook",
    "Events",
    "ServerLimits",
    "RouteLimits",
    "TokenLimits",
    "RouteNotFound",
    "MethodNotAllowed",
    "RateLimitExceeded",
    "TokenLimitExceeded",
    "ModelUnavailable",
    # AI (lazy)
    "ConversationContext",
    "Message",
    "MessageRole",
    "PromptTemplate",
    "TemplateVar",
    "ToolRegistry",
    "ToolResult",
    "tool",
    "ModelRouter",
    "ModelSpec",
    "RoutingStrategy",
    "SemanticCache",
    "SSEWriter",
    "sse_stream",
    "TokenBucket",
    "GlobalTokenBucket",
    "RateLimitMiddleware",
    # Middleware (lazy)
    "CORSMiddleware",
    "BearerAuthMiddleware",
    "APIKeyMiddleware",
    # Cache (lazy)
    "StaticCache",
    "RedisCache",
    "MemcachedCache",
]
