import json
from pathlib import Path

import pytest

from mac_health_checkup.core.config import get_config_value, require_int, reset_config_cache

MODULE_PATH = "tests/test_config.py"


def test_get_config_value_reads_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Purpose: Verify config overrides are loaded from the environment path.
    Ties: Exercises get_config_value and reset_config_cache.
    Inputs: Temporary config file and monkeypatched env var.
    Outputs: Assertions on override and fallback values.
    Side effects: Writes a temp file and updates env vars.
    Why: Ensures config lookup respects explicit config files.
    """
    try:
        payload = {"logging": {"max_lines": 900}}
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(payload), encoding="utf-8")

        monkeypatch.setenv("MAC_HEALTH_CHECKUP_CONFIG", str(config_path))
        reset_config_cache()

        assert get_config_value("logging.max_lines", 500, require_int(1, 2000)) == 900
        assert get_config_value("logging.truncate_len", 1000, require_int(100, 5000)) == 1000
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_get_config_value_reads_override failed: {exc}") from exc
