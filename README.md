# Mac Health Checkup

Mac Health Checkup is a macOS diagnostics dashboard that collects read only system signals and renders a resilient UI with clear fallbacks. The focus is on predictable parsing, strict typing, and operational guardrails so the project stays maintainable as it grows.

## Architecture overview

- `mac_health_checkup/core/config/` is the single source of truth for configuration, validation, and size limits.
- `mac_health_checkup/core/utils/shell.py` wraps every command with timeouts, retries, and clear failure messages.
- `mac_health_checkup/core/utils/loggers.py` emits structured logs with correlation ids and redaction.
- `mac_health_checkup/diagnostics/` contains IO heavy collectors with caching and strict typing.
- `mac_health_checkup/app/gui/sections/` contains small section renderers with minimal public surface area.
- `mac_health_checkup/app/gui/app.py` provides the Tk host and refresh loop for the dashboard.
- `mac_health_checkup/app/backend/snapshot.py` emits a stable JSON snapshot for native frontends.
- `swift-ui/` contains a SwiftUI macOS app that renders the same sections using the JSON snapshot backend.
- `benchmarks/` contains deterministic hot path benchmarks and profiling scripts.

## Design details worth scanning

- `mac_health_checkup/core/config/public.py` shows typed config parsing with validators and a safe override path.
- `mac_health_checkup/core/utils/shell.py` is the IO boundary with backoff, jitter, and bounded timeouts.
- `mac_health_checkup/app/gui/sections/display/parsing.py` normalizes noisy display output into stable rows.
- `mac_health_checkup/diagnostics/power.py` isolates power and thermal parsing with clear failure paths.
- `benchmarks/run.py` and `benchmarks/baseline.json` keep performance regressions visible.

## Setup

Requirements:

- macOS
- Python 3.10 or newer with Tkinter available

Build once:

```sh
make build
```

Manual setup if preferred:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Run

Single-file, press-run entrypoint (recommended):

```sh
python3 run.py
```

Headless agent API (no UI window, used for iOS pairing):

```sh
python3 run.py --agent
```

```sh
make run
```

Or directly:

```sh
python -m mac_health_checkup
```

One-click Mac agent (recommended for iOS pairing):

```sh
python3 run_mac_health_checkup.py
```

This starts the Mac agent API (headless, no window). To view the UI, either run the iOS app from Xcode or run the
native macOS SwiftUI UI (below).

CLI only mode:

```sh
python -m mac_health_checkup --cli
```

SwiftUI native UI (macOS):

```sh
python3 run_mac_health_checkup_ui.py
```

or:

```sh
make swift-run
```

The SwiftUI app calls the Python backend in snapshot mode (`python -m mac_health_checkup --snapshot-json`) and
renders the result using the same theme and section order from `config/config.json`.

## Mac agent API (for iOS)

iOS cannot run macOS collectors locally. Run the Mac agent API and connect from the iOS app.

1) Edit `config/config.json`:

- Set `api.enabled` to `true`
- Set `api.allow_lan` to `true` to allow iPhone access over your LAN
- By default, LAN mode requires TLS. If you insist on HTTP, set `api.allow_insecure_http_lan` to `true` (not recommended)
- Set `api.bind_host` to `0.0.0.0` to listen on all interfaces (keep `127.0.0.1` if you only want local access)
- Set `api.auth_token` to a strong random value

2) Start the server:

```sh
make serve
```

The agent serves `GET /v1/health` (no auth) and `GET /v1/snapshot` (Bearer token).

### Optional TLS + certificate pinning

If you use LAN access on an untrusted network, HTTPS prevents passive sniffing. The included iOS client supports
leaf certificate pinning so you can use a self-signed certificate without installing a trusted CA.

1) Generate a self-signed cert (writes to `.local/tls/`, which is git-ignored):

```sh
make tls-selfsigned
```

2) Enable TLS in `config/config.json`:

- Set `api.tls_enabled` to `true`
- Ensure `api.tls_cert_path` and `api.tls_key_path` match the generated files

3) Restart the agent:

```sh
make serve
```

On start, `--serve` prints the certificate fingerprint (sha256) and a pairing JSON blob that includes `pin`.

## iOS app (SwiftUI)

The native iOS client lives in `ios/MacHealthCheckupMobile/`.

Open `ios/MacHealthCheckupMobile/MacHealthCheckupMobile.xcodeproj` in Xcode and run on a device or simulator.
On first launch, pair by entering the agent URL and token (or import via QR / clipboard).

Notes:

- Local network access prompts are expected on first connect.
- The token is stored in Keychain, not in UserDefaults.
- For HTTPS with self-signed certs, paste the printed `pin` fingerprint into Settings to enable certificate pinning.

## Configuration

All runtime knobs are centralized in `config/config.json`. Override the path with `MAC_HEALTH_CHECKUP_CONFIG`. The file size limit can be tightened using `MAC_HEALTH_CHECKUP_CONFIG_MAX_BYTES`.

Key sections:

- `logging` for structured log fields and redaction
- `timeouts` for command and cache TTLs
- `retries` for backoff and jitter behavior
- `rate_limits` for UI refresh backpressure
- `benchmarks` for iteration counts and regression thresholds
- `gui` for layout, headers, and rendering limits

## Performance and profiling

Benchmarks run deterministic hot paths and compare against `benchmarks/baseline.json`:

```sh
make bench
```

Update the baseline after a deliberate performance change:

```sh
PYTHONPATH=. .venv/bin/python benchmarks/run.py --update
```

Profiling uses the same inputs and writes `benchmarks/profile.pstats`:

```sh
make profile
```

## Testing

Test categories include unit, integration, and an end to end smoke test for the refresh workflow.

```sh
make test
```

Type checking and linting:

```sh
make typecheck
make lint
```

## Troubleshooting

- Tkinter errors on launch: confirm the system Python includes Tk or install a framework build of Python.
- system_profiler failures: adjust `timeouts` and re run with `make run` to see structured logs.
- smartctl failures: set `fans.use_sudo` to false or run on a system where smartctl is available.
- CLI fallback: use `python -m mac_health_checkup --cli` if Tk is not available.

## Quality gates

CI enforces formatting, linting, type checking, tests with coverage, benchmarks, and security scans. Pre commit hooks mirror the same gates locally.

## Security and privacy

- No telemetry or analytics.
- Dependency auditing runs in CI with `pip-audit`.
- Secret scanning runs in CI and via pre commit using `.secrets.baseline`.
- Logs are structured and redacted based on `logging.redact_keys`.

## Release discipline

Changes are tracked in `CHANGELOG.md`. Versioning and release steps are defined in `RELEASE.md`.

## License

MIT. See `LICENSE`.
