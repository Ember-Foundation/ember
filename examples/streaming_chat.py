"""Streaming chat completions via SSE.

Demonstrates:
  - ai_route() with streaming=True
  - SSEResponse / sse_stream() helper
  - ConversationContext injection
  - PromptTemplate with variables
  - ModelRouter with fallback strategy
  - Token-aware rate limiting
  - Tool calling with ToolRegistry

Run:
    OPENAI_API_KEY=sk-... python examples/streaming_chat.py

Then test with:
    curl -N -X POST http://127.0.0.1:8000/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer test-key" \
      -d '{"messages": [{"role": "user", "content": "What is Python?"}], "stream": true}'
"""
import sys
import asyncio
sys.path.insert(0, ".")

from ember import (
    Ember,
    Request,
    JSONResponse,
    SSEResponse,
    ConversationContext,
    MessageRole,
    ModelRouter,
    ModelSpec,
    RoutingStrategy,
    PromptTemplate,
    TemplateVar,
    ToolRegistry,
    ToolResult,
    sse_stream,
    GlobalTokenBucket,
    RateLimitMiddleware,
    TokenLimits,
    BearerAuthMiddleware,
    Events,
)

# ── Tools ──────────────────────────────────────────────────────────────────────

tools = ToolRegistry()


@tools.register(description="Get the current date and time")
async def get_current_time() -> str:
    from datetime import datetime
    return datetime.now().isoformat()


@tools.register(description="Calculate the result of a mathematical expression")
async def calculate(expression: str) -> str:
    try:
        result = eval(expression, {"__builtins__": {}})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


# ── System prompt template ─────────────────────────────────────────────────────

system_template = PromptTemplate(
    template="You are a helpful AI assistant. Answer concisely: $question",
    variables=[TemplateVar("question", "The user's question", required=True)],
    system_prompt=(
        "You are a concise, helpful assistant. "
        "Use tools when needed. "
        "Format code with markdown code blocks."
    ),
)

# ── Model router ───────────────────────────────────────────────────────────────

model_router = ModelRouter(
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
            name="claude-3-5-haiku-20241022",
            provider="anthropic",
            endpoint="https://api.anthropic.com/v1/messages",
            api_key_env="ANTHROPIC_API_KEY",
            max_tokens=4096,
            context_window=200_000,
            cost_per_input_token=0.0008,
            cost_per_output_token=0.004,
            supports_tools=True,
        ),
    ],
    strategy=RoutingStrategy.FALLBACK,
)

# ── App ────────────────────────────────────────────────────────────────────────

app = Ember(
    model_router=model_router,
    token_limits=TokenLimits(
        tokens_per_minute=100_000,
        max_prompt_tokens=16_384,
        max_completion_tokens=4_096,
    ),
)

# Auth middleware
app.add_middleware(BearerAuthMiddleware(
    verify_fn=lambda token: token.startswith("test-") or bool(token),
    exclude_paths=["/health"],
))

# Rate limit middleware (uses GlobalTokenBucket registered via token_limits)
bucket = GlobalTokenBucket(capacity=100_000.0, refill_rate=100_000.0 / 60.0)
app.add_middleware(RateLimitMiddleware(global_bucket=bucket, estimate_from_body=True))


# ── Mock streaming generator (replace with real OpenAI/Anthropic call) ─────────

async def mock_stream(prompt: str):
    words = f"Great question about {prompt[:30]}! Python is a high-level, interpreted programming language known for its clean syntax and readability. It supports multiple paradigms including object-oriented, functional, and procedural programming.".split()
    for word in words:
        await asyncio.sleep(0.05)  # simulate model latency
        yield word + " "


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/models")
async def list_models() -> JSONResponse:
    models = [{"id": m.name, "provider": m.provider} for m in model_router._models]
    return JSONResponse({"models": models})


@app.ai_route(
    "/v1/chat/completions",
    methods=["POST"],
    streaming=True,
    tool_registry=tools,
)
async def chat_completions(
    request: Request,
    context: ConversationContext,
    model_router: ModelRouter,
) -> SSEResponse | JSONResponse:
    body = await request.ai_body()

    if not body.messages:
        return JSONResponse({"error": "messages required"}, status_code=400)

    # Add user message to context
    last_user = next(
        (m for m in reversed(body.messages) if m.get("role") == "user"),
        None,
    )
    if last_user:
        context.add_message(MessageRole.USER, last_user.get("content", ""))

    # Select model
    model = await model_router.select(request, context)

    # Build prompt
    question = last_user.get("content", "") if last_user else ""

    if body.stream:
        # Return SSE stream
        stream = mock_stream(question)
        return sse_stream(stream, token_bucket=bucket)
    else:
        # Non-streaming: collect all tokens
        tokens = []
        async for token in mock_stream(question):
            tokens.append(token)
        content = "".join(tokens)
        context.add_message(MessageRole.ASSISTANT, content)
        return JSONResponse({
            "id": "ember-chat-001",
            "model": model.name,
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": len(tokens)},
        })


@app.post("/v1/conversations/{conversation_id}/reset")
async def reset_conversation(request: Request, conversation_id: str) -> JSONResponse:
    return JSONResponse({"conversation_id": conversation_id, "reset": True})


# ── Hooks ──────────────────────────────────────────────────────────────────────

@app.hook(Events.BEFORE_SERVER_START)
async def startup(components) -> None:
    print(f"  Models: {[m.name for m in model_router._models]}")
    print(f"  Tools: {[t for t in tools._tools]}")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, workers=2, debug=True)
