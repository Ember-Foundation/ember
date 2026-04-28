## Summary

<!-- One or two sentences describing what this PR does and why. -->

## Type of Change

- [ ] `feat` — new feature
- [ ] `fix` — bug fix
- [ ] `docs` — documentation only
- [ ] `refactor` — code change that neither fixes a bug nor adds a feature
- [ ] `test` — adding or correcting tests
- [ ] `chore` — build, CI, dependency updates

## Changes Made

<!-- Bullet list of the specific changes. Reference files and functions where helpful. -->

-
-

## Test Coverage

<!-- Which test files cover this change? Did you add new tests? -->

- [ ] Existing tests pass (`pixi run test`)
- [ ] New tests added for new behaviour
- [ ] Manually tested with `pixi run example` or `pixi run task-manager`

## Checklist

- [ ] Branch is up to date with `main`
- [ ] Commit messages follow Conventional Commits format
- [ ] All `List[T]` types implement `ImplicitlyCopyable, Movable` with explicit `__copyinit__` / `__moveinit__`
- [ ] No new `alias` keywords — use `comptime` for Mojo ≥25.6 compatibility
- [ ] Public API changes are reflected in docs (`docs/api/`)
- [ ] Breaking changes are noted in `CHANGELOG.md` under `[Unreleased]`

## Related Issues

<!-- Closes #123 -->
