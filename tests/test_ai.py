import pytest
from ember.ai.context import ConversationContext, MessageRole
from ember.ai.prompt import PromptTemplate, TemplateVar
from ember.ai.tools import ToolRegistry, ToolCall
from ember.ai.routing import ModelRouter, ModelSpec, RoutingStrategy
from ember.ai.ratelimit.token_bucket import TokenBucket, GlobalTokenBucket
from ember.exceptions import MissingTemplateVar, ToolNotFound


class TestConversationContext:
    def test_add_messages(self):
        ctx = ConversationContext()
        ctx.add_message(MessageRole.USER, "Hello")
        ctx.add_message(MessageRole.ASSISTANT, "Hi there!")
        assert len(ctx.messages) == 2
        assert ctx.messages[0].role == MessageRole.USER

    def test_set_system(self):
        ctx = ConversationContext()
        ctx.set_system("You are helpful")
        assert ctx.messages[0].role == MessageRole.SYSTEM
        # Replace
        ctx.set_system("You are very helpful")
        assert len([m for m in ctx.messages if m.role == MessageRole.SYSTEM]) == 1
        assert "very" in ctx.messages[0].content

    def test_to_messages_list(self):
        ctx = ConversationContext()
        ctx.set_system("system prompt")
        ctx.add_message(MessageRole.USER, "question")
        msgs = ctx.to_messages_list()
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_trim_to_budget(self):
        ctx = ConversationContext(max_history_tokens=50)
        # Add many messages
        for i in range(20):
            ctx.add_message(MessageRole.USER, f"message {i} " * 5)
        # Should have been trimmed
        assert ctx.estimate_tokens() <= 50 + 20  # some slack for estimate

    def test_serialise_roundtrip(self):
        ctx = ConversationContext(conversation_id="test-123")
        ctx.set_system("Be helpful")
        ctx.add_message(MessageRole.USER, "Hello")
        ctx.add_message(MessageRole.ASSISTANT, "Hi!")

        data = ctx._serialise()
        restored = ConversationContext._deserialise(data)

        assert restored.conversation_id == "test-123"
        assert len(restored.messages) == 3

    def test_estimate_tokens(self):
        ctx = ConversationContext()
        ctx.add_message(MessageRole.USER, "Hello world")
        assert ctx.estimate_tokens() > 0


class TestPromptTemplate:
    def test_basic_render(self):
        t = PromptTemplate(
            "Answer this: $question",
            variables=[TemplateVar("question", "The question")],
        )
        result = t.render(question="What is Python?")
        assert "What is Python?" in result

    def test_missing_required_var(self):
        t = PromptTemplate(
            "Question: $question",
            variables=[TemplateVar("question", "The question", required=True)],
        )
        with pytest.raises(MissingTemplateVar):
            t.render()

    def test_default_var(self):
        t = PromptTemplate(
            "Lang: $lang",
            variables=[TemplateVar("lang", "Language", required=False, default="Python")],
        )
        result = t.render()
        assert "Python" in result

    def test_render_messages_with_system(self):
        t = PromptTemplate(
            "$question",
            variables=[TemplateVar("question", "Question")],
            system_prompt="You are helpful",
        )
        msgs = t.render_messages(question="Hi?")
        assert msgs[0]["role"] == "system"
        assert msgs[-1]["role"] == "user"

    def test_render_messages_with_history(self):
        ctx = ConversationContext()
        ctx.add_message(MessageRole.ASSISTANT, "Previous answer")
        t = PromptTemplate("$q", variables=[TemplateVar("q", "Question")])
        msgs = t.render_messages(history=ctx, q="New question")
        assert any(m["role"] == "assistant" for m in msgs)

    def test_estimate_tokens(self):
        t = PromptTemplate("This is a test prompt about $topic")
        estimate = t.estimate_tokens(topic="Python programming")
        assert estimate > 0


class TestToolRegistry:
    def setup_method(self):
        self.registry = ToolRegistry()

        @self.registry.register(description="Add two numbers")
        async def add(a: int, b: int) -> int:
            return a + b

        @self.registry.register(description="Greet a user")
        def greet(name: str) -> str:
            return f"Hello, {name}!"

    def test_register_and_list(self):
        assert len(self.registry) == 2
        assert self.registry.get("add") is not None
        assert self.registry.get("greet") is not None

    @pytest.mark.asyncio
    async def test_execute_async_tool(self):
        call = ToolCall(id="t1", name="add", arguments={"a": 3, "b": 4})
        result = await self.registry.execute(call)
        assert not result.is_error
        assert "7" in result.content

    @pytest.mark.asyncio
    async def test_execute_sync_tool(self):
        call = ToolCall(id="t2", name="greet", arguments={"name": "World"})
        result = await self.registry.execute(call)
        assert "World" in result.content
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        call = ToolCall(id="t3", name="nonexistent", arguments={})
        with pytest.raises(ToolNotFound):
            await self.registry.execute(call)

    def test_openai_specs(self):
        specs = self.registry.to_openai_specs()
        assert len(specs) == 2
        for spec in specs:
            assert "function" in spec
            assert "name" in spec["function"]

    def test_anthropic_specs(self):
        specs = self.registry.to_anthropic_specs()
        assert len(specs) == 2
        for spec in specs:
            assert "name" in spec
            assert "input_schema" in spec


class TestTokenBucket:
    def test_consume_within_capacity(self):
        bucket = TokenBucket(capacity=100.0, refill_rate=10.0)
        assert bucket.consume(50) is True
        assert bucket.consume(50) is True
        assert bucket.consume(1) is False  # exhausted

    def test_tokens_until_available(self):
        bucket = TokenBucket(capacity=100.0, refill_rate=10.0)
        bucket.consume(100)
        wait = bucket.tokens_until_available(10)
        assert wait > 0

    @pytest.mark.asyncio
    async def test_async_consume(self):
        bucket = GlobalTokenBucket(capacity=100.0, refill_rate=10.0)
        result = await bucket.consume_async(50)
        assert result is True

    def test_available_property(self):
        bucket = TokenBucket(capacity=100.0, refill_rate=10.0)
        assert bucket.available == pytest.approx(100.0, abs=1.0)


class TestModelRouter:
    def setup_method(self):
        self.router = ModelRouter(
            models=[
                ModelSpec(
                    name="model-a",
                    provider="openai",
                    endpoint="https://api.openai.com",
                    api_key_env="OPENAI_API_KEY",
                    cost_per_input_token=0.001,
                ),
                ModelSpec(
                    name="model-b",
                    provider="anthropic",
                    endpoint="https://api.anthropic.com",
                    api_key_env="ANTHROPIC_API_KEY",
                    cost_per_input_token=0.002,
                ),
            ],
            strategy=RoutingStrategy.FALLBACK,
        )

    @pytest.mark.asyncio
    async def test_fallback_selects_first(self):
        model = await self.router.select()
        assert model.name == "model-a"

    @pytest.mark.asyncio
    async def test_round_robin(self):
        self.router.strategy = RoutingStrategy.ROUND_ROBIN
        a = await self.router.select()
        b = await self.router.select()
        assert a.name != b.name

    @pytest.mark.asyncio
    async def test_cost_routing(self):
        self.router.strategy = RoutingStrategy.COST
        model = await self.router.select()
        assert model.name == "model-a"  # cheaper

    def test_mark_unavailable(self):
        self.router.mark_unavailable("model-a", duration_seconds=3600)
        assert len(self.router.available_models) == 1
        assert self.router.available_models[0].name == "model-b"

    @pytest.mark.asyncio
    async def test_all_unavailable_raises(self):
        from ember.exceptions import ModelUnavailable
        self.router.mark_unavailable("model-a")
        self.router.mark_unavailable("model-b")
        with pytest.raises(ModelUnavailable):
            await self.router.select()
