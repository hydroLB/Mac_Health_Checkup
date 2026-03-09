from __future__ import annotations

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/constants/__init__.py"

try:
    _cfg = get_config()
    BENCH_ITERATIONS = _cfg.benchmarks.iterations
    BENCH_REPEATS = _cfg.benchmarks.repeats
    BENCH_MAX_REGRESSION = _cfg.benchmarks.max_regression
except (RuntimeError, ValueError) as exc:
    raise RuntimeError(
        format_error(MODULE_PATH, "module_init", "Failed to load benchmark constants", exc)
    ) from exc
