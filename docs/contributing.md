# Contributing

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
- New features need a test

## Cython Hot Paths

After modifying any `.pyx` file:

```bash
python setup.py build_ext --inplace
```

## Pull Requests

1. Fork and create a feature branch
2. Write or update tests — all must pass
3. Open a PR against `master`

## Reporting Issues

- [Bug report](https://github.com/Ember-Foundation/ember/issues/new?template=bug_report.md) — include Python version, OS, and a minimal reproduction
- [Feature request](https://github.com/Ember-Foundation/ember/issues/new?template=feature_request.md)
