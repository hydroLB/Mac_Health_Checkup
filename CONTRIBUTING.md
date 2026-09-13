# Contributing

## Scope

This document defines how to contribute changes safely and consistently.

## Prerequisites

- macOS
- Python `3.11.x` (CI prefers the exact patch pinned in `.python-version`)
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
make preflight-swift-test
make preflight-ios
```

`make preflight-swift` is enough for Swift package builds and `swift run`. `make preflight-swift-test`, `make swift-test`, and `make ios-build` require full Xcode selected via `xcode-select`, not Command Line Tools alone.

## Local setup

```sh
make setup
```

`./start` will also rebuild `.venv` automatically if the repository moved or the existing virtualenv is no longer usable.

## Required checks

Run this before opening or updating a pull request:

```sh
make check
```

For most Python-only iterations, use:

```sh
make check-python
```

`make check` remains the full local and CI integration gate.
`make repo-hygiene` is included in both flows and blocks tracked caches, tracked local machine state, tracked secret material, missing recovery/bootstrap files, and accidental untracked shadow copies.

## Branch and PR workflow

1. Create a focused branch from `main`.
2. Keep diffs small and scoped to one concern.
3. Add or update tests when behavior changes.
4. Run `make check-python` while iterating and `make check` before opening or updating the pull request.
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

## Configuration changes

The source default and the copy shipped inside Python distributions are intentionally checked together. After
editing `config/config.json`, run:

```sh
make config-sync
make config-ref
```

Commit the source default, packaged copy, and generated reference in the same pull request. `make check-python`
fails if either generated artifact has drifted.

## Package validation

Build the installable Python artifacts with:

```sh
make build
```

The test suite also builds the wheel and source distribution, installs the wheel into an isolated environment, and
exercises the installed console entrypoint outside the source checkout.

## Reporting issues

- Use the bug report template for defects and regressions.
- Use the feature request template for proposals and enhancements.
- Include reproducible steps, expected behavior, and actual behavior.
