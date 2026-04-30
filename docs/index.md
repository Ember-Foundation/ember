---
layout: home

hero:
  name: "🔥 Ember"
  text: "The Python framework that runs at Go-tier speed"
  tagline: 100k+ RPS single-worker at 25 MB RSS · llhttp + Cython + io_uring · first-class LLM streaming · Python 3.12+
  actions:
    - theme: brand
      text: Get Started
      link: /guide/getting-started
    - theme: alt
      text: Tutorial
      link: /tutorial/01-hello-world
    - theme: alt
      text: Benchmarks
      link: /guide/performance#headline-numbers
    - theme: alt
      text: GitHub
      link: https://github.com/Ember-Foundation/ember

features:
  - icon: ⚡
    title: Fast by Default
    details: "llhttp C parser, Cython-compiled router/request/response, and an io_uring event loop. 100k+ RPS single-thread at p50 ~1.8 ms and just 25 MB RSS — 4.3× Express, 6.0× FastAPI, in the same league as Go Fiber on identical hardware."
    link: /guide/performance
    linkText: See benchmarks →

  - icon: 🧵
    title: Multi-Process Workers
    details: Fork-based workers share a SO_REUSEPORT socket. The kernel load-balances connections — no master-process overhead. Crashed workers auto-revive.
    link: /guide/concepts
    linkText: How it works →

  - icon: 🤖
    title: AI-First Primitives
    details: "ai_route(), SSEResponse, TokenStreamResponse, ConversationContext, ToolRegistry, ModelRouter, SemanticCache — every LLM-API building block, built in."
    link: /api/ai
    linkText: AI API reference →

  - icon: 🗄️
    title: Pluggable Caching
    details: StaticCache (zero overhead), RedisCache, MemcachedCache — one decorator arg, auto-connect lifecycle. No startup code.
    link: /api/caching
    linkText: Cache API →

  - icon: 🛠️
    title: CLI Included
    details: "ember new · ember dev · ember build · ember start · ember routes. Scaffold to production in five commands."
    link: /guide/cli
    linkText: CLI reference →

  - icon: 🌍
    title: Cross-Platform
    details: Linux/macOS use fork + SO_REUSEPORT. Windows falls back to single-process automatically. Every Cython module ships a pure-Python fallback.
---

<div style="max-width: 1152px; margin: 0 auto; padding: 0 24px;">

## Benchmarks at a glance

`GET /hello → "Hello, World!"`, single worker, k6 200 VUs / 20 s, on the same Intel i7-14700 box. Fiber pinned to one core (`GOMAXPROCS=1`) for fairness.

| Framework         |          RPS | p50 (ms) | p99 (ms) | Peak RSS |
| ----------------- | -----------: | -------: | -------: | -------: |
| **Fiber (Go)**    |  **149,007** |     1.16 |     3.89 |  **9 MB** |
| **Ember**         |  **101,411** |     1.79 |     4.98 | **25 MB** |
| Express (Node)    |       23,516 |     8.00 |    13.79 |   130 MB |
| NestJS (Node)     |       22,317 |     8.50 |    14.29 |   158 MB |
| FastAPI (Python)  |       16,879 |    10.20 |    27.63 |    48 MB |

Ember runs **6.0× FastAPI**, **4.3× Express**, and **4.5× NestJS** on identical hardware — and at **101k RPS / 25 MB RSS**, it's the only Python framework that breaks 100k single-thread without ballooning memory. → [Full benchmark methodology](/guide/performance#cross-framework-comparison)

## Hello, Ember

```python
from ember import Ember

app = Ember()

@app.get("/")
async def index():
    return {"hello": "world"}

app.run(host="0.0.0.0", port=8000, workers=4)
```

```bash
pip install ember-api
python app.py
```

## Built for AI workloads

```python
from ember import Ember, Request, SSEResponse, ConversationContext, sse_stream

app = Ember()

@app.ai_route("/v1/chat", methods=["POST"], streaming=True)
async def chat(request: Request, context: ConversationContext) -> SSEResponse:
    body = await request.json()
    context.add_message("user", body["message"])
    return sse_stream(token_stream(body["message"]))
```

`ai_route()`, `SSEResponse`, `ConversationContext`, `ToolRegistry`, `ModelRouter`, `SemanticCache`, token-bucket rate limits — all built in. → [AI API reference](/api/ai)

</div>
