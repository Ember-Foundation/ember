from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from ..exceptions import ModelUnavailable

if TYPE_CHECKING:
    from ..request import Request
    from .context import ConversationContext


class RoutingStrategy(StrEnum):
    LATENCY = "latency"
    COST = "cost"
    CAPABILITY = "capability"
    ROUND_ROBIN = "round_robin"
    FALLBACK = "fallback"


@dataclass
class ModelSpec:
    name: str
    provider: str
    endpoint: str
    api_key_env: str
    max_tokens: int = 4096
    context_window: int = 128_000
    cost_per_input_token: float = 0.0
    cost_per_output_token: float = 0.0
    supports_vision: bool = False
    supports_tools: bool = True
    timeout_seconds: float = 30.0
    weight: float = 1.0

    _available: bool = field(default=True, init=False, repr=False)
    _unavailable_until: float = field(default=0.0, init=False, repr=False)
    _avg_latency_ms: float = field(default=0.0, init=False, repr=False)
    _request_count: int = field(default=0, init=False, repr=False)

    @property
    def is_available(self) -> bool:
        if not self._available:
            if time.monotonic() >= self._unavailable_until:
                self._available = True
        return self._available

    def record_latency(self, latency_ms: float) -> None:
        if self._request_count == 0:
            self._avg_latency_ms = latency_ms
        else:
            # Exponential moving average
            self._avg_latency_ms = 0.9 * self._avg_latency_ms + 0.1 * latency_ms
        self._request_count += 1


class ModelRouter:
    """Routes requests to the appropriate LLM backend.

    Supports multiple strategies and automatic circuit-breaking when a
    model endpoint is unhealthy.

    Usage:
        router = ModelRouter(
            models=[
                ModelSpec("gpt-4o", provider="openai", endpoint="...", api_key_env="OPENAI_API_KEY"),
                ModelSpec("claude-3-5-sonnet-20241022", provider="anthropic",
                          endpoint="...", api_key_env="ANTHROPIC_API_KEY"),
            ],
            strategy=RoutingStrategy.FALLBACK,
        )
    """

    def __init__(
        self,
        models: list[ModelSpec],
        strategy: RoutingStrategy = RoutingStrategy.FALLBACK,
        health_check_interval: float = 30.0,
    ) -> None:
        self._models = models
        self.strategy = strategy
        self.health_check_interval = health_check_interval
        self._rr_index = 0

    @property
    def available_models(self) -> list[ModelSpec]:
        return [m for m in self._models if m.is_available]

    async def select(
        self,
        request: "Request | None" = None,
        context: "ConversationContext | None" = None,
    ) -> ModelSpec:
        available = self.available_models
        if not available:
            raise ModelUnavailable("all")

        if self.strategy == RoutingStrategy.FALLBACK:
            return available[0]

        if self.strategy == RoutingStrategy.ROUND_ROBIN:
            model = available[self._rr_index % len(available)]
            self._rr_index += 1
            return model

        if self.strategy == RoutingStrategy.LATENCY:
            return min(available, key=lambda m: m._avg_latency_ms or float("inf"))

        if self.strategy == RoutingStrategy.COST:
            return min(available, key=lambda m: m.cost_per_input_token + m.cost_per_output_token)

        if self.strategy == RoutingStrategy.CAPABILITY:
            return await self._select_by_capability(request, available)

        return available[0]

    async def _select_by_capability(
        self,
        request: "Request | None",
        available: list[ModelSpec],
    ) -> ModelSpec:
        if request is None:
            return available[0]
        content_type = request.headers.get(b"content-type", b"")
        if b"multipart" in content_type:
            vision_models = [m for m in available if m.supports_vision]
            if vision_models:
                return vision_models[0]
        return available[0]

    def mark_unavailable(self, model_name: str, duration_seconds: float = 60.0) -> None:
        for model in self._models:
            if model.name == model_name:
                model._available = False
                model._unavailable_until = time.monotonic() + duration_seconds
                break

    async def health_check(self) -> dict[str, bool]:
        results = {}
        for model in self._models:
            results[model.name] = model.is_available
        return results

    def get_model(self, name: str) -> ModelSpec | None:
        for m in self._models:
            if m.name == name:
                return m
        return None
