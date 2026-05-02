# 🔥 ember-api

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/Ember-Foundation/ember/blob/master/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](https://python.org)

**The fastest Python web framework** — engineered for raw speed and concurrency, with Cython hot paths, an `io_uring` event loop ([emberloop](https://pypi.org/project/emberloop/)), multi-process workers, and built-in TTL + single-flight caching ([ember-cache](https://pypi.org/project/ember-cache/)).

## Install

```bash
pip install ember-api               # core
pip install "ember-api[fast]"       # + uvloop + orjson
pip install "ember-api[all]"        # + Redis/Memcached/httpx
```

`ember-api` pulls in `emberloop` (HTTP protocol + event loop) and `ember-cache` (TTL + single-flight) automatically.

## Hello world

```python
from ember import Ember, JSONResponse

app = Ember()

@app.get("/")
async def hello(request):
    return JSONResponse({"hello": "world"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

## Why ember-api

| | ember-api | FastAPI | Express | NestJS |
|---|---|---|---|---|
| **Protocol** | llhttp + Cython + io_uring | ASGI / uvicorn | Node.js http | Node.js http |
| **Workers** | Fork + SO_REUSEPORT | Single process | cluster | cluster |
| **SSE streaming** | Native, zero-copy | via starlette | manual | manual |
| **AI primitives** | Built-in | none | none | none |

See the main [Ember docs](https://ember-foundation.github.io/ember/) for benchmarks, AI primitives, and full API reference.

## License

MIT
