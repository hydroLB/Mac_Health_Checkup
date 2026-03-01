# Configuration reference

Generated from the typed config registry and the repo default config file.

## Source of truth

- Default config: `config/config.json`
- Typed registry: `mac_health_checkup/core/config/models/`
- Parsing and validation: `mac_health_checkup/core/config/parsing/`

## Environment overrides

- `MAC_HEALTH_CHECKUP_CONFIG`: Override the config file path.
- `MAC_HEALTH_CHECKUP_CONFIG_MAX_BYTES`: Override the config file size limit in bytes.
- `MAC_HEALTH_CHECKUP_API_BIND_HOST`: Override `api.bind_host` at runtime (dev/CI).
- `MAC_HEALTH_CHECKUP_API_PORT`: Override `api.port` at runtime (0-65535; `0` picks a free port).

## Sections

Each section below lists leaf settings as dotted paths, their types, and the default values from the repo config.

### `colors`

Hold UI color configuration.

Validated by `mac_health_checkup.core.config.parsing.ui.parse_colors`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `colors.bad` | `str` | `"#e05d5d"` |  |
| `colors.banner_bad` | `str` | `"#dc3545"` |  |
| `colors.banner_good` | `str` | `"#28a745"` |  |
| `colors.banner_warn` | `str` | `"#ffc107"` |  |
| `colors.bg` | `str` | `"#12181f"` |  |
| `colors.fg` | `str` | `"#f3f7fb"` |  |
| `colors.field` | `str` | `"#e3eaf4"` |  |
| `colors.label` | `str` | `"#a8b3c4"` |  |
| `colors.ok` | `str` | `"#2fbf71"` |  |
| `colors.section` | `str` | `"#58a6ff"` |  |
| `colors.warn` | `str` | `"#d8a13a"` |  |

### `fonts`

Hold UI font configuration.

Validated by `mac_health_checkup.core.config.parsing.ui.parse_fonts`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `fonts.family_default` | `str` | `"Helvetica"` |  |
| `fonts.family_mono` | `str` | `"Consolas"` |  |
| `fonts.size_banner` | `int` | `18` |  |
| `fonts.size_field` | `int` | `13` |  |
| `fonts.size_section` | `int` | `16` |  |
| `fonts.size_tooltip` | `int` | `10` |  |
| `fonts.tooltip_bg` | `str` | `"#0f141a"` |  |
| `fonts.tooltip_fg` | `str` | `"#eef3f9"` |  |
| `fonts.weight_bold` | `str` | `"bold"` |  |
| `fonts.weight_normal` | `str` | `"normal"` |  |

### `ui`

Hold root UI window configuration.

Validated by `mac_health_checkup.core.config.parsing.ui.parse_ui`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `ui.window_size` | `str` | `"820x1180"` |  |
| `ui.window_title` | `str` | `"Mac Health Checkup"` |  |

### `logging`

Hold structured logging configuration.

Validated by `mac_health_checkup.core.config.parsing.observability.parse_logging`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `logging.component_field` | `str` | `"component"` |  |
| `logging.correlation_id_field` | `str` | `"corr_id"` |  |
| `logging.event_field` | `str` | `"event"` |  |
| `logging.format` | `str` | `"json"` |  |
| `logging.max_lines` | `int` | `500` |  |
| `logging.prefix` | `str` | `"[{timestamp} {level}{context}]"` |  |
| `logging.redact_keys` | `tuple[str, ...]` | `["password", "passcode", "secret", "token", "apikey", "authorization"]` |  |
| `logging.redact_replacement` | `str` | `"[REDACTED]"` |  |
| `logging.truncate_len` | `int` | `1000` |  |

### `retries`

Hold retry policy configuration.

Validated by `mac_health_checkup.core.config.parsing.runtime.parse_retries`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `retries.backoff_factor` | `float` | `2.0` |  |
| `retries.base_delay_ms` | `int` | `150` |  |
| `retries.enabled` | `bool` | `true` |  |
| `retries.jitter_ms` | `int` | `75` |  |
| `retries.max_attempts` | `int` | `2` |  |
| `retries.max_delay_ms` | `int` | `1000` |  |

### `rate_limits`

Hold UI rate limiting and backpressure settings.

Validated by `mac_health_checkup.core.config.parsing.runtime.parse_rate_limits`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `rate_limits.refresh_min_interval_ms` | `int` | `200` |  |
| `rate_limits.ui_queue_max_items` | `int` | `200` |  |

### `io`

Hold IO configuration settings.

Validated by `mac_health_checkup.core.config.parsing.runtime.parse_io`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `io.file_read_max_bytes` | `int` | `1048576` |  |
| `io.pty_read_max_bytes` | `int` | `65536` |  |

### `shutdown`

Hold graceful shutdown timing configuration.

Validated by `mac_health_checkup.core.config.parsing.runtime.parse_shutdown`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `shutdown.graceful_timeout_sec` | `int` | `2` |  |
| `shutdown.thread_join_timeout_sec` | `int` | `1` |  |

### `benchmarks`

Hold benchmarking configuration values.

Validated by `mac_health_checkup.core.config.parsing.runtime.parse_benchmarks`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `benchmarks.iterations` | `int` | `200` |  |
| `benchmarks.max_regression` | `float` | `0.3` |  |
| `benchmarks.repeats` | `int` | `5` |  |

### `timeouts`

Hold timeout configuration for diagnostics and caching.

Validated by `mac_health_checkup.core.config.parsing.runtime.parse_timeouts`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `timeouts.cache_ttl` | `int` | `30` |  |
| `timeouts.default_cmd_timeout` | `int` | `10` |  |
| `timeouts.display_cache_ttl` | `int` | `8` |  |
| `timeouts.istats_timeout` | `int` | `5` |  |
| `timeouts.network_cache_ttl` | `int` | `12` |  |
| `timeouts.network_quality_timeout` | `int` | `15` |  |
| `timeouts.performance_cache_ttl` | `int` | `5` |  |
| `timeouts.power_ioreg_cache_ttl` | `int` | `5` |  |
| `timeouts.power_sp_cache_ttl` | `int` | `8` |  |
| `timeouts.powermetrics_timeout` | `int` | `8` |  |
| `timeouts.smartctl_timeout` | `int` | `10` |  |
| `timeouts.snapshot_backend_timeout_sec` | `int` | `60` |  |
| `timeouts.softwareupdate_cache_ttl` | `int` | `21600` |  |
| `timeouts.softwareupdate_timeout` | `int` | `30` |  |
| `timeouts.sudo_pty_timeout` | `int` | `10` |  |

### `api`

Hold backend API server configuration for native frontends.

Validated by `mac_health_checkup.core.config.parsing.features.parse_api`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `api.allow_insecure_http_lan` | `bool` | `false` |  |
| `api.allow_lan` | `bool` | `false` |  |
| `api.auth_ban_seconds` | `int` | `120` |  |
| `api.auth_token` | `str` | `"change-me"` |  |
| `api.bind_host` | `str` | `"127.0.0.1"` | Can be overridden by env var MAC_HEALTH_CHECKUP_API_BIND_HOST. |
| `api.blocked_auth_tokens` | `list[str]` | `["change-me", "changeme", "password", "token"]` |  |
| `api.enabled` | `bool` | `false` |  |
| `api.max_auth_failures_per_minute` | `int` | `10` |  |
| `api.min_auth_token_length` | `int` | `24` |  |
| `api.pairing_qr_enabled` | `bool` | `true` |  |
| `api.port` | `int` | `7878` | Can be overridden by env var MAC_HEALTH_CHECKUP_API_PORT. |
| `api.rate_limit_requests_per_minute` | `int` | `120` |  |
| `api.request_timeout_sec` | `int` | `15` |  |
| `api.tls_cert_path` | `str` | `".local/tls/agent-cert.pem"` |  |
| `api.tls_enabled` | `bool` | `false` |  |
| `api.tls_key_path` | `str` | `".local/tls/agent-key.pem"` |  |

### `fans`

Hold fan diagnostics configuration.

Validated by `mac_health_checkup.core.config.parsing.features.parse_fans`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `fans.use_sudo` | `bool` | `false` |  |

### `thresholds`

Hold health threshold values for classifying metrics.

Validated by `mac_health_checkup.core.config.parsing.features.parse_thresholds`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `thresholds.backup_bad_days` | `int` | `30` |  |
| `thresholds.backup_warn_days` | `int` | `7` |  |
| `thresholds.disk_free_bad_percent` | `float` | `5.0` |  |
| `thresholds.disk_free_warn_percent` | `float` | `15.0` |  |
| `thresholds.memory_free_bad_percent` | `float` | `10.0` |  |
| `thresholds.memory_free_warn_percent` | `float` | `20.0` |  |
| `thresholds.rssi_bad_dbm` | `int` | `-80` |  |
| `thresholds.rssi_warn_dbm` | `int` | `-70` |  |
| `thresholds.temp_bad_c` | `float` | `90.0` |  |
| `thresholds.temp_warn_c` | `float` | `75.0` |  |

### `gui`

Hold detailed GUI configuration.

Validated by `mac_health_checkup.core.config.parsing.features.parse_gui`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `gui.auto_refresh_ms` | `int` | `10000` |  |
| `gui.bytes_per_du` | `float` | `512000.0` |  |
| `gui.card_bg` | `str` | `"#1a212a"` |  |
| `gui.card_border` | `str` | `"#313d4b"` |  |
| `gui.card_max_height` | `int` | `420` |  |
| `gui.card_relaxed_height` | `int` | `520` |  |
| `gui.content_wrap` | `int` | `760` |  |
| `gui.devices_headers` | `list[str]` | `["Bus", "Device"]` |  |
| `gui.disp_body_max_rows` | `int` | `16` |  |
| `gui.disp_body_min_rows` | `int` | `8` |  |
| `gui.display_headers` | `list[str]` | `["Name", "Resolution", "Mirror", "Connection", "Refresh", "Transport"]` |  |
| `gui.display_name_keywords` | `list[str]` | `list[len=15]` |  |
| `gui.drag_scroll_divisor` | `int` | `12` |  |
| `gui.fans_refresh_ms` | `int` | `5000` |  |
| `gui.indent_spaces` | `int` | `4` |  |
| `gui.layout_breakpoint_width` | `int` | `760` |  |
| `gui.layout_min_width` | `int` | `50` |  |
| `gui.layout_retry_ms` | `int` | `50` |  |
| `gui.max_devices_lines` | `int` | `80` |  |
| `gui.peripheral_allow_keywords` | `list[str]` | `["keyboard", "mouse", "trackpad", "receiver", "gamepad", "controller"]` |  |
| `gui.peripheral_max_name_len` | `int` | `28` |  |
| `gui.peripheral_skip_keywords` | `list[str]` | `["hub", "billboard", "bus"]` |  |
| `gui.processes_max_rows` | `int` | `10` |  |
| `gui.refresh_helper_max_samples` | `int` | `600` |  |
| `gui.refresh_helper_sample_secs` | `float` | `1.0` |  |
| `gui.refresh_helper_target_samples` | `int` | `5` |  |
| `gui.refresh_helper_timeout_sec` | `int` | `4` |  |
| `gui.scrollable_rows` | `dict[str, int]` | `{"devices": 14, "processes": 12, "startup": 14}` |  |
| `gui.section_padx` | `int` | `4` |  |
| `gui.section_pady` | `int` | `3` |  |
| `gui.section_rows` | `list[tuple[str, str, str]]` | `list[len=17]` |  |
| `gui.skip_display_noise` | `list[str]` | `list[len=7]` |  |
| `gui.ssd_text_max_lines` | `int` | `10` |  |
| `gui.ssd_text_min_lines` | `int` | `5` |  |
| `gui.startup_max_rows` | `int` | `30` |  |
| `gui.table_max_visible_rows` | `int` | `3` |  |
| `gui.table_min_col_width` | `int` | `80` |  |
| `gui.table_row_height` | `int` | `22` |  |
| `gui.token_norm_map` | `dict[str, str]` | `{"lan": "ethernet"}` |  |
| `gui.ui_queue_poll_ms` | `int` | `50` |  |
| `gui.window_max_height` | `int` | `1300` |  |
| `gui.window_max_width` | `int` | `1150` |  |

### `display_transport`

Hold display transport estimation configuration.

Validated by `mac_health_checkup.core.config.parsing.features.parse_display_transport`.

| Key | Type | Default | Notes |
|---|---|---:|---|
| `display_transport.default_bpp` | `int` | `24` |  |
| `display_transport.overhead_factor` | `float` | `1.15` |  |
