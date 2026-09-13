# Release Process

## Versioning policy

Semantic versioning is intended for tagged releases. Public behavior changes or API shifts update the major or minor version. Internal refactors that do not change behavior use patch increments.

Current repository state:

- `main` should be treated as unreleased development head until a tag is cut.
- `pyproject.toml` records the next planned package version, not proof that a public release already exists.
- Historical changelog versions are untagged development milestones, not published artifacts.
- The SwiftUI application is currently source-run only; there is no signed or notarized app bundle.

## Release steps

1. Update the version in `pyproject.toml` and move relevant `CHANGELOG.md` notes from `Unreleased` into a dated release section.
2. From a clean checkout, run `make setup` and `make check`. Native Swift/iOS checks require full Xcode selected via `xcode-select`, not Command Line Tools alone.
3. Run `make build` to create the Python wheel and source distribution, inspect their contents, install the wheel into an empty virtualenv, and run `mac-health-checkup --help` outside the checkout.
4. Update the benchmark baseline only when a reviewed performance change is intentional.
5. For a macOS binary release, add and verify an app-bundle archive, Developer ID signing, notarization, stapling, and checksum workflow before publishing any artifact. Until then, publish source/Python artifacts only.
6. Create a signed Git tag, push it, publish the matching release notes and checksums, then verify installation from the published artifact.
