# emberloop

io_uring event loop + Cython HTTP/1.1 protocol layer for the [Ember](https://github.com/Ember-Foundation/ember) web framework — usable on its own.

## What's inside

- **`ember.eventloop`** — `io_uring` async event loop on Linux, falls back to uvloop / asyncio elsewhere. Auto-installs the fastest backend available.
- **`ember.protocol`** — Cython HTTP/1.1 parser backed by [llhttp](https://github.com/nodejs/llhttp), zero-copy header/body callbacks, keep-alive aware.
- **`ember.request`** — Cython `Request` and `Stream` objects with cdef-typed fields.
- **`ember.response`** — `Response`, `JSONResponse`, `StreamingResponse`, `SSEResponse`, `TokenStreamResponse`, `RedirectResponse`. Cython hot path.
- **`ember.headers`** — Cython `Headers` mapping with bytes-native key/value access.

## Install

```bash
pip install emberloop         # binary wheel
pip install "emberloop[fast]" # + uvloop on non-Linux
```

Linux wheels include the `io_uring` backend (kernel ≥ 5.1 required at runtime). macOS wheels skip the uring extension and fall back to uvloop / asyncio.

## Use

```python
from ember.eventloop import install_best_event_loop
from ember.protocol.cprotocol import HTTPParser
from ember.response import JSONResponse

install_best_event_loop()
# ... wire up your own server loop
```

For a complete server, see the higher-level [`ember-api`](https://pypi.org/project/ember-api/) package.

## License

MIT
