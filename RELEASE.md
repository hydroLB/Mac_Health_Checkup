# Release Process

## Versioning policy

Semantic versioning is used. Public behavior changes or API shifts update the major or minor version. Internal refactors that do not change behavior use patch increments.

## Release steps

1. Update the version in `pyproject.toml`.
2. Add release notes to `CHANGELOG.md`.
3. Run `make lint`, `make typecheck`, `make test`, and `make bench`.
4. Update the benchmark baseline if performance changes are intentional.
5. Tag the release and push the tag.
