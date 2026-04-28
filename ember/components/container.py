"""
Type-based dependency injection container.
In production, compiled by Cython via components.pxd.

Resolution order:
  1. ephemeral_index (per-request objects: Request, Route, ConversationContext)
  2. index (singleton-like objects: ModelRouter, GlobalTokenBucket, etc.)
  3. builder registry (factory callables registered at startup)
"""
from __future__ import annotations
from typing import Any, Callable


class ComponentsEngine:
    """Resolves handler dependencies by Python type.

    Two index tiers:
    - index: long-lived components registered at startup (singletons)
    - ephemeral_index: per-request components cleared after each response

    Both dicts are keyed by Python type objects, not strings, so lookup
    is a single id() comparison after hash.
    """

    def __init__(self) -> None:
        self.index: dict[type, Any] = {}
        self.ephemeral_index: dict[type, Any] = {}
        self._builders: dict[type, Callable] = {}

    def add(self, component: Any, component_type: type | None = None) -> None:
        """Register a singleton component."""
        key = component_type or type(component)
        self.index[key] = component

    def add_builder(self, component_type: type, builder: Callable) -> None:
        """Register a factory that creates a per-request component on first access."""
        self._builders[component_type] = builder

    def add_ephemeral(self, component: Any, component_type: type | None = None) -> None:
        """Register a per-request component. Cleared by reset() after each response."""
        key = component_type or type(component)
        self.ephemeral_index[key] = component

    def get(self, component_type: type) -> Any | None:
        """Resolve a component by type. Returns None if not registered."""
        result = self.ephemeral_index.get(component_type)
        if result is not None:
            return result
        result = self.index.get(component_type)
        if result is not None:
            return result
        builder = self._builders.get(component_type)
        if builder is not None:
            instance = builder()
            self.ephemeral_index[component_type] = instance
            return instance
        return None

    def reset(self) -> None:
        """Clear per-request (ephemeral) components after each response."""
        self.ephemeral_index.clear()

    def clone(self) -> "ComponentsEngine":
        """Create a child engine that inherits singletons but has its own ephemeral scope."""
        child = ComponentsEngine()
        child.index = self.index
        child._builders = self._builders
        return child

    def inject_ai_defaults(
        self,
        context: Any = None,
        bucket: Any = None,
        model_router: Any = None,
    ) -> None:
        """Bulk-inject AI components at route registration time."""
        if context is not None:
            from ..ai.context import ConversationContext
            self.add(context, ConversationContext)
        if bucket is not None:
            from ..ai.ratelimit.token_bucket import GlobalTokenBucket
            self.add(bucket, GlobalTokenBucket)
        if model_router is not None:
            from ..ai.routing import ModelRouter
            self.add(model_router, ModelRouter)
