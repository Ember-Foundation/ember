"""ember.ai — AI / LLM building blocks.

Pure-Python primitives (context, prompt, tools, routing, semantic cache) load
eagerly. Cython-backed sub-extensions (`ratelimit.token_bucket`, `sse.sse_writer`)
load lazily on first attribute access via PEP 562 — apps that only need
conversation/tool primitives don't pay for them on cold start.
"""
import importlib as _importlib

# Eager: pure-Python, cheap to import.
from .context import ConversationContext, Message, MessageRole, ToolCall
from .prompt  import PromptTemplate, TemplateVar
from .tools   import ToolRegistry, ToolDefinition, ToolResult, tool
from .routing import ModelRouter, ModelSpec, RoutingStrategy
from .cache   import SemanticCache

# Lazy: each entry triggers loading the named submodule (and its .so) on first
# access. Saves ~1.5 MB on cold start when these are unused.
_LAZY: dict[str, str] = {
    "TokenBucket":         ".ratelimit",
    "GlobalTokenBucket":   ".ratelimit",
    "RateLimitMiddleware": ".ratelimit",
    "SSEWriter":           ".sse",
    "sse_stream":          ".sse",
}


def __getattr__(name: str):
    mod_path = _LAZY.get(name)
    if mod_path is None:
        raise AttributeError(f"module 'ember.ai' has no attribute {name!r}")
    mod = _importlib.import_module(mod_path, __name__)
    val = getattr(mod, name)
    globals()[name] = val
    return val


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY))


__all__ = [
    "ConversationContext", "Message", "MessageRole", "ToolCall",
    "PromptTemplate", "TemplateVar",
    "ToolRegistry", "ToolDefinition", "ToolResult", "tool",
    "ModelRouter", "ModelSpec", "RoutingStrategy",
    "SemanticCache",
    "SSEWriter", "sse_stream",
    "TokenBucket", "GlobalTokenBucket", "RateLimitMiddleware",
]
