"""
Ember — AI-API-first async HTTP framework.

Inspired by Vibora. Built for LLM workloads:
  - First-class SSE streaming for token output
  - Native async with uvloop
  - Cython hot-path compilation
  - Multi-process SO_REUSEPORT workers + thread pool for CPU inference
  - Token-aware rate limiting
  - Conversation context management
  - Prompt templates, tool calling, model routing, semantic cache
"""
try:
    from .eventloop import install_best_event_loop
    install_best_event_loop()
except Exception:
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass

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
from .ai import (
    ConversationContext,
    Message,
    MessageRole,
    PromptTemplate,
    TemplateVar,
    ToolRegistry,
    ToolResult,
    tool,
    ModelRouter,
    ModelSpec,
    RoutingStrategy,
    SemanticCache,
    SSEWriter,
    sse_stream,
    TokenBucket,
    GlobalTokenBucket,
    RateLimitMiddleware,
)
from .middleware import CORSMiddleware, BearerAuthMiddleware, APIKeyMiddleware
from .cache import StaticCache, RedisCache, MemcachedCache

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
    # AI
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
    # Middleware
    "CORSMiddleware",
    "BearerAuthMiddleware",
    "APIKeyMiddleware",
    # Cache
    "StaticCache",
    "RedisCache",
    "MemcachedCache",
]
