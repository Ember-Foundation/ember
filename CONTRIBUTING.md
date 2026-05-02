# Contributing to Ember

Ember is a uv workspace with three packages under `packages/`:

- **`ember-api`** — framework layer (router, middleware, AI, sessions, CLI, workers)
- **`ember-cache`** — TTL + single-flight cache, Redis/Memcached backends
- **`emberloop`** — io_uring event loop + Cython HTTP/1.1 protocol layer

## Dev Setup

```bash
git clone https://github.com/Ember-Foundation/ember.git
cd ember

# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync the workspace — installs all 3 packages editable + dev deps
uv sync

# Build Cython extensions (emberloop + ember-api)
uv run --directory packages/emberloop python setup.py build_ext --inplace
uv run --directory packages/ember-api  python setup.py build_ext --inplace
```

On Linux, install `liburing-dev` first so the io_uring backend builds:

```bash
sudo apt-get install -y liburing-dev   # Debian/Ubuntu
```

## Running Tests

```bash
uv run pytest                                  # all packages
uv run pytest packages/emberloop/tests         # one package
uv run pytest packages/ember-cache/tests/test_cache.py::TestTTLCache  # one class
```

## Code Style

- Python 3.12+, type hints everywhere
- No comments unless the _why_ is non-obvious
- Keep `.pyx` / `.pxd` in sync when adding `cdef` fields

## Cython Hot Paths

| Module | Package | File |
|--------|---------|------|
| Headers | emberloop | `packages/emberloop/src/ember/headers/headers.pyx` |
| Request | emberloop | `packages/emberloop/src/ember/request/request.pyx` |
| Response | emberloop | `packages/emberloop/src/ember/response/response.pyx` |
| Protocol | emberloop | `packages/emberloop/src/ember/protocol/cprotocol.pyx` |
| io_uring loop | emberloop | `packages/emberloop/src/ember/eventloop/uring.pyx` |
| Router | ember-api | `packages/ember-api/src/ember/router/router.pyx` |
| SSE writer | ember-api | `packages/ember-api/src/ember/ai/sse/sse_writer.pyx` |
| Token bucket | ember-api | `packages/ember-api/src/ember/ai/ratelimit/token_bucket.pyx` |

Each has a `.py` pure-Python fallback used when Cython is not installed.

After modifying a `.pyx` file, rebuild that package:

```bash
uv run --directory packages/<package-name> python setup.py build_ext --inplace
```

### Build flags

Local Linux/macOS release builds are stripped (`-Wl,-s`) by default — debug
symbols are removed at link time, shrinking the `.so` files ~80% on disk.
This is invisible at runtime but means `gdb` / `perf` traces won't show
Cython function names. To preserve symbols:

```bash
EMBER_DEBUG=1 uv run --directory packages/emberloop python setup.py build_ext --inplace
```

CIBUILDWHEEL builds keep symbols at build time; auditwheel/delocate strip
them later in their own steps.

## Pull Requests

1. Fork and create a feature branch
2. Write or update tests in the appropriate package
3. Run `uv run pytest` — all tests must pass
4. Open a PR against `master`

## Releasing a Package

Each package releases independently via tag triggers:

| Package | Tag pattern | Workflow |
|---|---|---|
| emberloop | `emberloop-v*.*.*` | `.github/workflows/publish-emberloop.yml` |
| ember-cache | `ember-cache-v*.*.*` | `.github/workflows/publish-ember-cache.yml` |
| ember-api | `ember-api-v*.*.*` | `.github/workflows/publish-ember-api.yml` |

Bump the version in `packages/<name>/pyproject.toml`, tag, push.

## Reporting Bugs

Use the [bug report template](https://github.com/Ember-Foundation/ember/issues/new?template=bug_report.md).
Include Python version, OS, the package(s) affected, and a minimal reproduction.
