from __future__ import annotations
from dataclasses import dataclass
from string import Template
from typing import Any, TYPE_CHECKING

from ..exceptions import MissingTemplateVar

if TYPE_CHECKING:
    from .context import ConversationContext


@dataclass
class TemplateVar:
    name: str
    description: str
    required: bool = True
    default: str | None = None


class PromptTemplate:
    """String template for LLM prompts with variable substitution.

    Supports OpenAI and Anthropic message formats out of the box.
    Model-specific overrides allow per-provider prompt tuning without
    changing the application logic.

    Example:
        template = PromptTemplate(
            "You are a helpful assistant. The user asked: $question",
            variables=[TemplateVar("question", "User's question")],
            system_prompt="You are concise and accurate.",
        )
        messages = template.render_messages(question="What is Python?")
    """

    def __init__(
        self,
        template: str,
        variables: list[TemplateVar] | None = None,
        system_prompt: str | None = None,
        model_hints: dict[str, str] | None = None,
    ) -> None:
        self._template = Template(template)
        self.variables = variables or []
        self.system_prompt = system_prompt
        self.model_hints = model_hints or {}
        self._var_map = {v.name: v for v in self.variables}

    def render(self, **kwargs: Any) -> str:
        """Render the template with the given keyword arguments."""
        self._validate(kwargs)
        substitutions = {}
        for var in self.variables:
            val = kwargs.get(var.name, var.default)
            substitutions[var.name] = str(val) if val is not None else ""
        # Pass through extra kwargs too
        for k, v in kwargs.items():
            if k not in substitutions:
                substitutions[k] = str(v)
        return self._template.safe_substitute(substitutions)

    def _validate(self, kwargs: dict[str, Any]) -> None:
        for var in self.variables:
            if var.required and var.name not in kwargs and var.default is None:
                raise MissingTemplateVar(var.name)

    def render_messages(
        self,
        history: "ConversationContext | None" = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Build an OpenAI-compatible messages list.

        Order: system (if any) → history messages → rendered user turn.
        If model is provided and a model_hint exists, uses the hint as
        the user message instead of the main template.
        """
        messages: list[dict] = []

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        if history:
            messages.extend(history.to_messages_list())

        user_content: str
        if model and model in self.model_hints:
            hint_template = Template(self.model_hints[model])
            user_content = hint_template.safe_substitute(kwargs)
        else:
            user_content = self.render(**kwargs)

        messages.append({"role": "user", "content": user_content})
        return messages

    def estimate_tokens(self, **kwargs: Any) -> int:
        """Rough token estimate before calling the model."""
        rendered = self.render(**kwargs)
        total = len(rendered) // 4
        if self.system_prompt:
            total += len(self.system_prompt) // 4 + 4
        return total
