---
layout: home

title: "Ember — The fastest Python web framework"
titleTemplate: ":title"
description: "Ember is a Python web framework that hits 112,000 RPS single-thread at 25 MB RSS. Built on Cython, llhttp, and io_uring. AI-first with native SSE, conversation context, semantic cache, and token-aware rate limiting."

head:
  - - meta
    - name: keywords
      content: "Python web framework, Python HTTP framework, fast Python framework, async Python framework, Python LLM framework, Python AI API, Python io_uring, FastAPI alternative, Cython HTTP, Python SSE streaming, Python web server"
  - - meta
    - name: author
      content: "Ember Foundation"
  - - meta
    - property: og:type
      content: website
  - - meta
    - property: og:title
      content: "Ember — The Python framework that hits 112k RPS"
  - - meta
    - property: og:description
      content: "The fastest Python web framework — engineered for raw speed and concurrency. 112k RPS single-thread, 25 MB RSS, llhttp + Cython + io_uring."
  - - meta
    - property: og:image
      content: "https://ember-foundation.github.io/ember/og-image.svg"
  - - meta
    - property: og:url
      content: "https://ember-foundation.github.io/ember/"
  - - meta
    - name: twitter:card
      content: summary_large_image
  - - meta
    - name: twitter:title
      content: "Ember — 112k RPS Python web framework"
  - - meta
    - name: twitter:description
      content: "The fastest Python web framework. 6× faster than FastAPI, 4× faster than Express, in 25 MB RSS."
  - - meta
    - name: twitter:image
      content: "https://ember-foundation.github.io/ember/og-image.svg"
  - - link
    - rel: canonical
      href: "https://ember-foundation.github.io/ember/"
  - - script
    - type: application/ld+json
    - {}
    - |
      {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Ember",
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Linux, macOS, Windows",
        "description": "The fastest Python web framework. 112k RPS single-thread at 25 MB RSS, 21k RPS on real PostgreSQL CRUD with TTL+single-flight caching built in.",
        "url": "https://ember-foundation.github.io/ember/",
        "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
        "softwareVersion": "0.2.1",
        "license": "https://opensource.org/licenses/MIT",
        "programmingLanguage": "Python"
      }

hero:
  name: "🔥 Ember"
  text: "112k RPS. 25 MB RAM. Pure Python."
  tagline: "The fastest Python web framework — built on llhttp, Cython, and io_uring. 6× faster than FastAPI on `/hello`, 10× faster on real PostgreSQL CRUD."
  image:
    src: /logo.svg
    alt: Ember Logo
  actions:
    - theme: brand
      text: Get Started →
      link: /guide/getting-started
    - theme: alt
      text: Tutorial
      link: /tutorial/01-hello-world
    - theme: alt
      text: ⚡ Benchmarks
      link: /guide/performance#cross-framework-comparison
    - theme: alt
      text: GitHub
      link: https://github.com/Ember-Foundation/ember

features:
  - icon: ⚡
    title: 112,000 RPS single-thread
    details: "llhttp C parser, Cython hot paths, and an io_uring event loop. p50 1.68 ms, p99 4.35 ms, 25 MB RSS — only Go Fiber goes faster, and only barely."
    link: /guide/performance
    linkText: See benchmarks →

  - icon: 🤖
    title: AI-first by design
    details: "ai_route(), SSEResponse, ConversationContext, ToolRegistry, ModelRouter, SemanticCache, token-aware rate limits. Every LLM-API primitive is built in."
    link: /api/ai
    linkText: AI reference →

  - icon: 🪶
    title: 25 MB at idle, 25 MB under load
    details: "Tunable io_uring buffer pool, lazy AI/cache imports, in-process workers=1 mode. Fits in containers Node.js can't even boot in."
    link: /guide/performance#whats-new-in-v02-rss-shrink-100k-rps
    linkText: How we shrunk it →

  - icon: 🧵
    title: Multi-process scaling
    details: "Fork-based workers share a SO_REUSEPORT socket. Kernel load-balances connections — no master overhead. Crashed workers auto-revive."
    link: /guide/concepts
    linkText: How it works →

  - icon: 🌊
    title: Native SSE & streaming
    details: "SSEResponse, sse_stream(), TokenStreamResponse — zero-copy LLM token output. Built for chat/completions, not bolted on like ASGI."
    link: /api/sse
    linkText: SSE API →

  - icon: 🛠️
    title: Production from day one
    details: "Graceful shutdown, dead-worker revival, keep-alive reaper, tunable kernel backlog, Redis & Memcached caches, CORS / Bearer / API-Key middleware."
    link: /guide/deployment
    linkText: Deploy →
---

<style>
:root {
  --vp-home-hero-name-color: transparent;
  --vp-home-hero-name-background: -webkit-linear-gradient(120deg, #ff6b35 30%, #ffb84d);
  --vp-home-hero-image-background-image: linear-gradient(-45deg, #ff6b35 50%, #ffb84d 50%);
  --vp-home-hero-image-filter: blur(48px);
}
.tagline-stat {
  display: inline-block;
  padding: 0.15rem 0.6rem;
  margin: 0 0.2rem;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  background: rgba(255, 107, 53, 0.10);
  color: var(--vp-c-brand-1);
  border-radius: 6px;
}
.bench-callout {
  margin: 4rem auto 2rem;
  padding: 2rem 2.25rem;
  max-width: 1152px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(255, 107, 53, 0.06) 0%, rgba(255, 184, 77, 0.04) 100%);
  border: 1px solid var(--vp-c-divider);
}
.bench-callout h2 {
  margin: 0 0 0.5rem 0;
  border-top: none;
  padding-top: 0;
  font-size: 1.6rem;
  letter-spacing: -0.02em;
}
.bench-callout .lede {
  color: var(--vp-c-text-2);
  margin: 0 0 1.5rem 0;
}
.bench-callout table {
  margin: 0;
  width: 100%;
}
.bench-callout th { text-align: left; }
.bench-callout td.num { text-align: right; font-variant-numeric: tabular-nums; }
.bench-callout .ember-row td {
  background: rgba(255, 107, 53, 0.08);
  font-weight: 600;
}
.code-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin: 3rem auto 2rem;
  max-width: 1152px;
}
@media (max-width: 800px) {
  .code-grid { grid-template-columns: 1fr; }
}
.use-cases {
  max-width: 1152px;
  margin: 4rem auto 2rem;
}
.use-cases h2 {
  text-align: center;
  font-size: 1.8rem;
  letter-spacing: -0.02em;
  margin-bottom: 0.5rem;
}
.use-cases .center-lede {
  text-align: center;
  color: var(--vp-c-text-2);
  margin: 0 0 2.5rem 0;
}
.use-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.25rem;
}
@media (max-width: 800px) {
  .use-grid { grid-template-columns: 1fr; }
}
.use-card {
  padding: 1.5rem;
  border-radius: 12px;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg-soft);
}
.use-card h3 { margin: 0 0 0.5rem 0; font-size: 1.1rem; }
.use-card p { margin: 0; color: var(--vp-c-text-2); font-size: 0.92rem; }
.cta {
  text-align: center;
  margin: 5rem auto 2rem;
  max-width: 700px;
}
.cta h2 {
  font-size: 2rem;
  letter-spacing: -0.025em;
  margin-bottom: 0.5rem;
}
.cta p {
  color: var(--vp-c-text-2);
  margin: 0 0 1.5rem 0;
}
.cta-buttons a {
  display: inline-block;
  margin: 0 0.5rem;
  padding: 0.6rem 1.4rem;
  border-radius: 8px;
  font-weight: 600;
  text-decoration: none;
  transition: opacity 0.2s;
}
.cta-buttons a:hover { opacity: 0.85; }
.cta-buttons .primary {
  background: var(--vp-c-brand-1);
  color: white;
}
.cta-buttons .secondary {
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-1);
  border: 1px solid var(--vp-c-divider);
}
</style>

<div class="bench-callout">

## Benchmarks — same machine, identical workload

<p class="lede">Single-worker hello-world on an Intel i7-14700, k6 200 VUs / 20 s, 0% errors.</p>

| Framework | RPS | p50 (ms) | p99 (ms) | Peak RSS |
|---|---:|---:|---:|---:|
| **Fiber (Go)** | **140,993** | 1.21 | 3.96 | **9 MB** |
| <span class="ember-row-label">**Ember (Python)**</span> | **112,177** | **1.68** | **4.35** | **25 MB** |
| Express (Node) | 26,357 | 7.09 | 13.57 | 131 MB |
| NestJS (Node) | 23,528 | 8.08 | 13.75 | 158 MB |
| FastAPI (Python) | 17,517 | 9.45 | 30.86 | 49 MB |

<style>
table tr:has(.ember-row-label) td {
  background: rgba(255, 107, 53, 0.08);
  font-weight: 600;
}
</style>

Ember is **6.4× FastAPI**, **4.3× Express**, and **4.8× NestJS** on identical hardware — at 25 MB RSS, half FastAPI's footprint and **5× lighter than Node**. Fiber stays ahead on raw throughput, but the gap is now ~20% rather than 75%.

[Full methodology and reproducible scripts →](/guide/performance#cross-framework-comparison)

</div>

<div class="code-grid">

<div>

### Hello, Ember

```python
from ember import Ember

app = Ember()

@app.get("/")
async def index():
    return {"hello": "world"}

app.run(host="0.0.0.0", port=8000)
```

```bash
pip install ember-api
python app.py
# 112k RPS at 25 MB RSS. No tuning required.
```

</div>

<div>

### Built for AI workloads

```python
from ember import (
    Ember, Request, SSEResponse,
    ConversationContext, sse_stream
)

app = Ember()

@app.ai_route("/v1/chat",
              methods=["POST"], streaming=True)
async def chat(
    request: Request,
    context: ConversationContext,
) -> SSEResponse:
    body = await request.json()
    context.add_message("user", body["message"])
    return sse_stream(token_stream(body["message"]))
```

</div>

</div>

<div class="use-cases">

## Built for the workloads that matter

<p class="center-lede">From microservices to LLM gateways — Ember handles them all.</p>

<div class="use-grid">

<div class="use-card">

### LLM API gateways

Native `ai_route()`, `ConversationContext`, `ModelRouter` with fallback strategies, `SemanticCache` for vector lookups, and token-bucket rate limiting that counts tokens — not requests.

</div>

<div class="use-card">

### High-throughput APIs

112k RPS single-thread means a 4-worker box reliably handles **400k+ RPS**. Cython router with O(1) static dispatch, llhttp parser, multishot recv on Linux 5.1+.

</div>

<div class="use-card">

### Edge & sidecar deployments

25 MB RSS at idle means Ember fits in containers most Python frameworks can't even boot in. Ideal for sidecars, Functions, Kubernetes microservices.

</div>

<div class="use-card">

### Real-time streaming

SSE-first design: `SSEResponse`, `sse_stream()`, `TokenStreamResponse` — zero-copy from generator to wire. Built for chat completions, log tails, live dashboards.

</div>

<div class="use-card">

### Background-job APIs

Multi-process workers with `SO_REUSEPORT`, kernel load-balancing, dead-worker revival, graceful shutdown, keep-alive reaper. Production semantics out of the box.

</div>

<div class="use-card">

### Replace FastAPI without rewriting

Decorator-based routing, type-hint dependency injection, async handlers, JSON responses with orjson — the patterns you already know, but **6× faster**.

</div>

</div>

</div>

<div class="cta">

## Ship faster APIs.

<p>Pip-installable. Cython-compiled wheels for Linux x86_64/aarch64 and macOS arm64/x86_64.</p>

<div class="cta-buttons">
  <a class="primary" href="/ember/guide/getting-started">Read the docs →</a>
  <a class="secondary" href="https://github.com/Ember-Foundation/ember">Star on GitHub</a>
</div>

</div>
