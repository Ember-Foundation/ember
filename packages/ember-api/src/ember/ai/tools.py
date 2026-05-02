from __future__ import annotations
import inspect
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from ..exceptions import ToolNotFound


@dataclass
class ParameterSchema:
    name: str
    type: str
    description: str
    required: bool = True
    enum: list[Any] | None = None

    def to_json_schema(self) -> dict:
        schema: dict = {"type": self.type, "description": self.description}
        if self.enum:
            schema["enum"] = self.enum
        return schema


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: list[ParameterSchema]
    handler: Callable
    is_async: bool = field(init=False)

    def __post_init__(self) -> None:
        self.is_async = inspect.iscoroutinefunction(self.handler)

    def to_openai_spec(self) -> dict:
        props = {p.name: p.to_json_schema() for p in self.parameters}
        required = [p.name for p in self.parameters if p.required]
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }

    def to_anthropic_spec(self) -> dict:
        props = {p.name: p.to_json_schema() for p in self.parameters}
        required = [p.name for p in self.parameters if p.required]
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        }


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    @classmethod
    def from_openai_delta(cls, delta: dict) -> "ToolCall":
        fn = delta.get("function", {})
        args = fn.get("arguments", "{}")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        return cls(
            id=delta.get("id", str(uuid.uuid4())),
            name=fn.get("name", ""),
            arguments=args,
        )


@dataclass
class ToolResult:
    tool_call_id: str
    content: str
    is_error: bool = False

    def to_openai_message(self) -> dict:
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }


class ToolRegistry:
    """Registry of callable tools for LLM function/tool calling.

    Usage:
        registry = ToolRegistry()

        @registry.register(description="Get current weather for a city")
        async def get_weather(city: str, units: str = "celsius") -> str:
            ...

        specs = registry.to_openai_specs()
        result = await registry.execute(tool_call)
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        fn: Callable | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        parameters: list[ParameterSchema] | None = None,
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            tool_desc = description or (func.__doc__ or "").strip()
            if parameters is not None:
                params = parameters
            else:
                params = _infer_parameters(func)
            self._tools[tool_name] = ToolDefinition(
                name=tool_name,
                description=tool_desc,
                parameters=params,
                handler=func,
            )
            return func

        if fn is not None:
            return decorator(fn)
        return decorator

    async def execute(self, call: ToolCall) -> ToolResult:
        definition = self._tools.get(call.name)
        if definition is None:
            raise ToolNotFound(call.name)
        try:
            if definition.is_async:
                result = await definition.handler(**call.arguments)
            else:
                result = definition.handler(**call.arguments)
            content = result if isinstance(result, str) else json.dumps(result)
            return ToolResult(tool_call_id=call.id, content=content)
        except Exception as e:
            return ToolResult(
                tool_call_id=call.id,
                content=f"Error: {e}",
                is_error=True,
            )

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def to_openai_specs(self) -> list[dict]:
        return [t.to_openai_spec() for t in self._tools.values()]

    def to_anthropic_specs(self) -> list[dict]:
        return [t.to_anthropic_spec() for t in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)


def tool(
    fn: Callable | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable:
    """Module-level decorator for ad-hoc tool registration.

    Usage:
        @tool(description="Search the web for a query")
        async def web_search(query: str) -> str:
            ...
    """
    _registry = ToolRegistry()
    return _registry.register(fn, name=name, description=description)


_PYTHON_TO_JSON_TYPE = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "Any": "string",
}


def _infer_parameters(fn: Callable) -> list[ParameterSchema]:
    sig = inspect.signature(fn)
    params = []
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            type_name = "string"
        else:
            ann_name = getattr(annotation, "__name__", str(annotation))
            type_name = _PYTHON_TO_JSON_TYPE.get(ann_name, "string")
        required = param.default is inspect.Parameter.empty
        params.append(ParameterSchema(
            name=pname,
            type=type_name,
            description=f"Parameter '{pname}'",
            required=required,
        ))
    return params
