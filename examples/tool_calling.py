"""Tool/function calling example.

Demonstrates:
  - ToolRegistry with complex tool definitions
  - ParameterSchema with enum validation
  - Async and sync tool handlers
  - Error handling in tool execution

Run:
    python examples/tool_calling.py
"""
import sys
import asyncio
sys.path.insert(0, ".")

from ember import (
    Ember,
    Request,
    JSONResponse,
    ToolRegistry,
    ToolCall,
)
from ember.ai.tools import ParameterSchema

tools = ToolRegistry()

# ── Tool definitions ────────────────────────────────────────────────────────────

@tools.register(
    name="get_weather",
    description="Get current weather for a city",
    parameters=[
        ParameterSchema("city", "string", "City name, e.g. 'London'"),
        ParameterSchema("units", "string", "Temperature units", required=False, enum=["celsius", "fahrenheit"]),
    ],
)
async def get_weather(city: str, units: str = "celsius") -> dict:
    # Mock weather data
    return {
        "city": city,
        "temperature": 22 if units == "celsius" else 72,
        "units": units,
        "condition": "partly cloudy",
    }


@tools.register(
    name="search_web",
    description="Search the web for information",
    parameters=[
        ParameterSchema("query", "string", "Search query"),
        ParameterSchema("max_results", "integer", "Max results to return", required=False),
    ],
)
async def search_web(query: str, max_results: int = 5) -> list:
    # Mock search results
    return [
        {"title": f"Result {i+1} for: {query}", "url": f"https://example.com/{i+1}"}
        for i in range(min(max_results, 3))
    ]


@tools.register(description="Execute Python code safely")
def execute_code(code: str) -> str:
    try:
        # Extremely restricted execution
        result = eval(code, {"__builtins__": {"abs": abs, "len": len, "range": range}})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


# ── App ────────────────────────────────────────────────────────────────────────

app = Ember()


@app.get("/tools")
async def list_tools() -> JSONResponse:
    return JSONResponse({
        "tools": tools.to_openai_specs(),
        "count": len(tools),
    })


@app.post("/tools/execute")
async def execute_tool(request: Request) -> JSONResponse:
    data = await request.json()
    call = ToolCall(
        id=data.get("id", "call_001"),
        name=data.get("name", ""),
        arguments=data.get("arguments", {}),
    )
    result = await tools.execute(call)
    return JSONResponse({
        "tool_call_id": result.tool_call_id,
        "content": result.content,
        "is_error": result.is_error,
    })


@app.get("/tools/openai-spec")
async def openai_spec() -> JSONResponse:
    return JSONResponse({"tools": tools.to_openai_specs()})


@app.get("/tools/anthropic-spec")
async def anthropic_spec() -> JSONResponse:
    return JSONResponse({"tools": tools.to_anthropic_specs()})


async def _demo():
    """Run a quick demonstration without starting the server."""
    print("Tools registered:", list(tools._tools.keys()))
    print()

    # Execute weather tool
    result = await tools.execute(ToolCall(
        id="test_1",
        name="get_weather",
        arguments={"city": "Paris", "units": "celsius"},
    ))
    print(f"Weather result: {result.content}")

    # Execute search tool
    result = await tools.execute(ToolCall(
        id="test_2",
        name="search_web",
        arguments={"query": "Python async frameworks", "max_results": 2},
    ))
    print(f"Search result: {result.content}")

    # Execute code tool
    result = await tools.execute(ToolCall(
        id="test_3",
        name="execute_code",
        arguments={"code": "sum(range(10))"},
    ))
    print(f"Code result: {result.content}")

    # Test unknown tool error handling
    result = await tools.execute(ToolCall(id="test_4", name="unknown_tool", arguments={}))
    print(f"Unknown tool: {result.is_error=}, {result.content!r}")


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        asyncio.run(_demo())
    else:
        app.run(host="127.0.0.1", port=8001, workers=1, debug=True)
