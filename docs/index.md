---
layout: home

hero:
  name: "🔥 Ember"
  text: "AI-API-first async HTTP framework"
  tagline: Cython hot paths · multi-process workers · first-class LLM streaming · Python 3.11+
  actions:
    - theme: brand
      text: Get Started
      link: /guide/getting-started
    - theme: alt
      text: Tutorial
      link: /tutorial/01-hello-world
    - theme: alt
      text: GitHub
      link: https://github.com/Ember-Foundation/ember

features:
  - title: Fast by Default
    details: llhttp C parser + Cython-compiled router, request, response, and headers. ~2,650 RPS at p50 16ms — faster than Express on a single machine.
  - title: Multi-Process Workers
    details: Fork-based workers share a SO_REUSEPORT socket. Kernel load-balances connections. No master-process overhead. Auto-revives crashed workers.
  - title: AI-First Primitives
    details: ai_route(), SSEResponse, TokenStreamResponse, ConversationContext, ToolRegistry, ModelRouter, SemanticCache — all built in.
  - title: Pluggable Caching
    details: StaticCache (zero overhead), RedisCache, MemcachedCache — one decorator arg, auto-connect lifecycle. No startup code.
  - title: CLI Included
    details: ember new · ember dev · ember build · ember start · ember routes. From scaffold to production in five commands.
  - title: Cross-Platform
    details: Linux/macOS use fork + SO_REUSEPORT. Windows falls back to single-process automatically. Every Cython module has a pure-Python fallback.
---
