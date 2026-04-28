# Contributing to Ember

## Dev Setup

```bash
git clone https://github.com/Ember-Foundation/ember.git
cd ember
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Optional: compile Cython extensions for full performance
pip install cython
python setup.py build_ext --inplace
```

## Running Tests

```bash
pytest
```

## Code Style

- Python 3.12+, type hints everywhere
- No comments unless the _why_ is non-obvious
- Keep `.pyx` / `.pxd` in sync when adding `cdef` fields

## Cython Hot Paths

The following modules have `.pyx` / `.pxd` counterparts compiled with Cython:

| Module | File |
|--------|------|
| Headers | `ember/headers/headers.pyx` |
| Request | `ember/request/request.pyx` |
| Response | `ember/response/response.pyx` |
| Router | `ember/router/router.pyx` |
| Protocol | `ember/protocol/cprotocol.pyx` |
| SSE writer | `ember/ai/sse/sse_writer.pyx` |
| Token bucket | `ember/ai/ratelimit/token_bucket.pyx` |

Each has a `.py` pure-Python fallback used when Cython is not installed.

After modifying a `.pyx` file, rebuild:

```bash
python setup.py build_ext --inplace
```

## Pull Requests

1. Fork and create a feature branch
2. Write or update tests
3. Run `pytest` — all tests must pass
4. Open a PR against `master`

## Reporting Bugs

Use the [bug report template](https://github.com/Ember-Foundation/ember/issues/new?template=bug_report.md).  
Include Python version, OS, and a minimal reproduction.
