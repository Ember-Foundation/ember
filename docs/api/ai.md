# AI Primitives

Ember's AI layer is designed for building LLM-backed APIs with minimal boilerplate.

---

## ConversationContext

Per-session message history. Auto-injected into `ai_route()` handlers.

```python
from ember import ConversationContext, MessageRole

@app.ai_route("/v1/chat", methods=["POST"])
async def chat(request, context: ConversationContext):
    context.add_message(MessageRole.USER, "Hello")
    context.add_message(MessageRole.ASSISTANT, "Hi there!")
    history = context.get_messages()    # list[Message]
    context.clear()                     # reset history
```

---

## PromptTemplate

String templates with named variables and system prompt attachment.

```python
from ember import PromptTemplate, TemplateVar

template = PromptTemplate(
    template="Answer this question concisely: $question",
    variables=[TemplateVar("question", "The user's question", required=True)],
    system_prompt="You are a helpful assistant.",
)

rendered = template.render(question="What is Python?")
# → "Answer this question concisely: What is Python?"
```

---

## ToolRegistry

Register Python functions as LLM tools. Generates OpenAI and Anthropic specs automatically.

```python
from ember import ToolRegistry, ToolResult
from ember.ai.tools import ParameterSchema

tools = ToolRegistry()

@tools.register(description="Get current weather for a city")
async def get_weather(city: str, units: str = "celsius") -> dict:
    return {"city": city, "temp": 22, "units": units}

@tools.register(
    name="search_web",
    description="Search the web",
    parameters=[
        ParameterSchema("query", "string", "Search query"),
        ParameterSchema("limit", "integer", "Max results", required=False),
    ],
)
async def search(query: str, limit: int = 5) -> list:
    return [{"title": f"Result for {query}"}]
```

Execute a tool call:

```python
from ember.ai.tools import ToolCall

result = await tools.execute(ToolCall(
    id="call_001",
    name="get_weather",
    arguments={"city": "Paris"},
))
print(result.content)    # "{'city': 'Paris', 'temp': 22, 'units': 'celsius'}"
print(result.is_error)   # False
```

Generate specs:

```python
tools.to_openai_specs()      # list[dict] for OpenAI function calling
tools.to_anthropic_specs()   # list[dict] for Anthropic tools
```

---

## ModelRouter

Select a model based on strategy, cost, or latency.

```python
from ember import ModelRouter, ModelSpec, RoutingStrategy

router = ModelRouter(
    models=[
        ModelSpec(
            name="gpt-4o-mini",
            provider="openai",
            endpoint="https://api.openai.com/v1/chat/completions",
            api_key_env="OPENAI_API_KEY",
            max_tokens=4096,
            context_window=128_000,
            cost_per_input_token=0.00015,
            cost_per_output_token=0.0006,
            supports_tools=True,
        ),
        ModelSpec(
            name="claude-haiku",
            provider="anthropic",
            endpoint="https://api.anthropic.com/v1/messages",
            api_key_env="ANTHROPIC_API_KEY",
            max_tokens=4096,
            context_window=200_000,
            cost_per_input_token=0.0008,
            cost_per_output_token=0.004,
        ),
    ],
    strategy=RoutingStrategy.FALLBACK,  # or CHEAPEST, FASTEST, ROUND_ROBIN
)
```

Pass `model_router=router` to `Ember()` to inject it into `ai_route()` handlers.

---

## SemanticCache

Vector-similarity cache for AI responses — returns a cached answer when the incoming query is semantically close to a previous one.

```python
from ember.ai.cache import SemanticCache

semantic_cache = SemanticCache(
    similarity_threshold=0.92,
    embed_fn=my_embed_function,  # async fn(text: str) -> list[float]
    ttl=3600,
)

@app.ai_route("/v1/chat", methods=["POST"], semantic_cache=semantic_cache)
async def chat(request, context): ...
```

---

## Token Limits

```python
from ember import TokenLimits

@app.ai_route(
    "/v1/chat",
    methods=["POST"],
    token_limits=TokenLimits(
        tokens_per_minute=60_000,
        tokens_per_day=1_000_000,
        max_prompt_tokens=16_384,
        max_completion_tokens=4_096,
    ),
)
async def chat(request, context): ...
```

Exceeding limits returns `429` with `{"error": "token_limit_exceeded"}`.
