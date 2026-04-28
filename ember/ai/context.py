from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    pass


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    role: MessageRole
    content: str
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None
    token_count: int | None = None

    def to_dict(self) -> dict:
        d: dict = {"role": str(self.role), "content": self.content}
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.name, "arguments": str(tc.arguments)}}
                for tc in self.tool_calls
            ]
        return d

    def estimate_tokens(self) -> int:
        # 4 chars ≈ 1 token + 4 overhead tokens per message
        return len(self.content) // 4 + 4


@dataclass
class ConversationContext:
    """Stateful conversation history with automatic token-budget trimming.

    Serialisable to/from a session backend. Injected into route handlers
    via the ComponentsEngine.
    """

    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    max_history_tokens: int = 8192
    _token_count: int = field(default=0, init=False, repr=False)

    def add_message(
        self,
        role: MessageRole | str,
        content: str,
        tool_call_id: str | None = None,
        tool_calls: list[ToolCall] | None = None,
    ) -> Message:
        msg = Message(
            role=MessageRole(role),
            content=content,
            tool_call_id=tool_call_id,
            tool_calls=tool_calls,
        )
        msg.token_count = msg.estimate_tokens()
        self.messages.append(msg)
        self._token_count += msg.token_count
        self._maybe_trim()
        return msg

    def _maybe_trim(self) -> None:
        if self._token_count > self.max_history_tokens:
            self.trim_to_budget(self.max_history_tokens)

    def trim_to_budget(self, budget: int) -> None:
        """Drop oldest non-system messages until total token count <= budget."""
        system_msgs = [m for m in self.messages if m.role == MessageRole.SYSTEM]
        other_msgs = [m for m in self.messages if m.role != MessageRole.SYSTEM]

        while other_msgs and self._token_count > budget:
            removed = other_msgs.pop(0)
            self._token_count -= (removed.token_count or removed.estimate_tokens())

        self.messages = system_msgs + other_msgs

    def set_system(self, content: str) -> None:
        """Replace or set the system message (always kept at index 0)."""
        system_msgs = [m for m in self.messages if m.role == MessageRole.SYSTEM]
        if system_msgs:
            old = system_msgs[0]
            self._token_count -= (old.token_count or old.estimate_tokens())
            system_msgs[0].content = content
            system_msgs[0].token_count = system_msgs[0].estimate_tokens()
            self._token_count += system_msgs[0].token_count
        else:
            self.messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=content,
                token_count=len(content) // 4 + 4,
            ))
            self._token_count += self.messages[0].token_count or 0

    def to_messages_list(self) -> list[dict]:
        """OpenAI-compatible messages array."""
        return [m.to_dict() for m in self.messages]

    def estimate_tokens(self) -> int:
        if self._token_count == 0:
            self._token_count = sum(
                (m.token_count or m.estimate_tokens()) for m in self.messages
            )
        return self._token_count

    @classmethod
    async def load(cls, session: Any, conversation_id: str) -> "ConversationContext":
        """Load conversation from session backend, or create new if not found."""
        data = await session.get(f"conv:{conversation_id}")
        if data:
            return cls._deserialise(data)
        return cls(conversation_id=conversation_id)

    async def save(self, session: Any) -> None:
        await session.set(f"conv:{self.conversation_id}", self._serialise())

    def _serialise(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "messages": [
                {
                    "role": str(m.role),
                    "content": m.content,
                    "tool_call_id": m.tool_call_id,
                    "token_count": m.token_count,
                }
                for m in self.messages
            ],
            "metadata": self.metadata,
            "max_history_tokens": self.max_history_tokens,
        }

    @classmethod
    def _deserialise(cls, data: dict) -> "ConversationContext":
        ctx = cls(
            conversation_id=data["conversation_id"],
            metadata=data.get("metadata", {}),
            max_history_tokens=data.get("max_history_tokens", 8192),
        )
        for m in data.get("messages", []):
            msg = Message(
                role=MessageRole(m["role"]),
                content=m["content"],
                tool_call_id=m.get("tool_call_id"),
                token_count=m.get("token_count"),
            )
            ctx.messages.append(msg)
            ctx._token_count += msg.token_count or msg.estimate_tokens()
        return ctx
