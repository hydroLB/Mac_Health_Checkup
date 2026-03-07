# Contributing

## Scope

This document defines how to contribute changes safely and consistently.

## Prerequisites

- macOS
- Python `3.11.14` (see `.python-version`)
- Xcode (full app) with iOS SDKs for Apple build targets
- Xcode command line tools selected via `xcode-select`

Verify Apple toolchain:

```sh
xcodebuild -version
xcode-select -p
swift --version
```

Optional explicit preflight checks:

```sh
make preflight-swift
make preflight-ios
```

## Local setup

```sh
make setup
```

## Required checks

Run this before opening or updating a pull request:

```sh
make check
```

`make check` is the single required quality gate command for local and CI validation.
`make repo-hygiene` is included in that gate and blocks tracked caches, tracked local machine state, tracked secret material, and missing recovery/bootstrap files.

## Branch and PR workflow

1. Create a focused branch from `main`.
2. Keep diffs small and scoped to one concern.
3. Add or update tests when behavior changes.
4. Run `make check`.
5. Open a pull request using the PR template.

## Commit guidance

- Use imperative, concise commit subjects.
- Prefer one logical change per commit.
- Do not commit secrets, local caches, or generated noise.
- Keep GitHub recovery-ready: if the local machine disappeared, the tracked repo should still contain everything needed for `make setup` and `./start`.

## Dependency updates

Use lockfile-aware commands:

```sh
make deps-lock
make deps-check
```

If lockfiles change, include them in the same pull request as the dependency input changes.

## Reporting issues

- Use the bug report template for defects and regressions.
- Use the feature request template for proposals and enhancements.
- Include reproducible steps, expected behavior, and actual behavior.
