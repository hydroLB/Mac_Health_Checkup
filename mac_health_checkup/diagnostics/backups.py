from __future__ import annotations

import datetime as dt
import re

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error, safe_run
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/backups.py"

_TM_TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2}-\d{6})")


class TimeMachineDiagnostics:
    """
    Summary
    Collect Time Machine backup recency using read-only `tmutil`.

    Inputs
    None.

    Outputs
    Dict with latest backup timestamp and age.

    Side effects
    Executes `tmutil` commands.

    Error handling
    Returns `ok=false` when Time Machine appears unavailable or no backups are found.

    Ties to other methods
    Used by the Backups section (`mac_health_checkup/app/gui/sections/backups.py`).

    Why this exists
    Backup recency is one of the highest leverage health signals for preventing data loss.
    """

    _cache = Cache(get_config().timeouts.cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch Time Machine status with caching.

        Inputs
        None.

        Outputs
        Diagnostics dict with latest backup age and raw output.

        Side effects
        Executes bounded `tmutil` calls when cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by Backups section refresh loops.

        Why this exists
        Avoids repeated `tmutil` execution on short UI refresh intervals.
        """
        try:
            return cached_fetch(
                TimeMachineDiagnostics._cache, "time_machine", TimeMachineDiagnostics._fetch_uncached
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "TimeMachineDiagnostics.fetch", "Failed to fetch Time Machine", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch Time Machine status without caching.

        Inputs
        None.

        Outputs
        Diagnostics dict.

        Side effects
        Executes `tmutil latestbackup` and `tmutil status`.

        Error handling
        Never raises for missing tools; returns `ok=false` with guidance when unavailable.

        Ties to other methods
        Wrapped by `fetch` via `cached_fetch`.

        Why this exists
        Time Machine may be disabled on some systems; the dashboard should degrade gracefully.
        """
        logger = get_diagnostics_logger()
        context = new_context("TimeMachineDiagnostics")
        try:
            timeout = int(get_config().timeouts.default_cmd_timeout)
            latest_out, latest_err = safe_run(
                ["tmutil", "latestbackup"], context="tmutil_latestbackup", allow_sudo=False, timeout=timeout
            )
            status_out, _status_err = safe_run(
                ["tmutil", "status"], context="tmutil_status", allow_sudo=False, timeout=timeout
            )
            latest = (latest_out or "").strip()
            timestamp = _extract_tm_timestamp(latest)
            latest_dt = _parse_tm_timestamp(timestamp) if timestamp else None
            age_days = _age_days(latest_dt) if latest_dt else None
            running = _tm_is_running(status_out or "")

            ok = latest_dt is not None
            if not ok:
                logger.info(
                    "no time machine backup found",
                    event="backup_missing",
                    context=context,
                    payload={"error": latest_err or ""},
                )
            guidance = None
            if not ok:
                guidance = "No Time Machine backups detected. If you rely on backups, enable Time Machine and run an initial backup."
            return {
                "ok": ok,
                "latest_backup_path": latest if latest else None,
                "latest_backup_timestamp": timestamp,
                "latest_backup_age_days": age_days,
                "running": running,
                "raw_latest": latest_out or "",
                "raw_status": status_out or "",
                "error": latest_err or "",
                "guidance": guidance,
            }
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError) as exc:
            logger.warning(
                "time machine collection failed",
                event="backup_error",
                context=context,
                payload={"error": str(exc), "error_type": type(exc).__name__},
            )
            return {
                "ok": False,
                "error": format_error(
                    MODULE_PATH,
                    "TimeMachineDiagnostics._fetch_uncached",
                    "Failed to collect Time Machine status",
                    exc,
                ),
            }


def _extract_tm_timestamp(path_text: str) -> str | None:
    """
    Summary
    Extract a Time Machine timestamp from a latestbackup path.

    Inputs
    path_text: `tmutil latestbackup` output.

    Outputs
    Timestamp string like `YYYY-MM-DD-HHMMSS`, or None.

    Side effects
    None.

    Error handling
    Never raises; returns None when missing.

    Ties to other methods
    Used by `TimeMachineDiagnostics._fetch_uncached`.

    Why this exists
    `tmutil latestbackup` returns a path; the timestamp component is the most useful signal for recency.
    """
    match = _TM_TIMESTAMP_RE.search(path_text or "")
    if not match:
        return None
    return match.group(1)


def _parse_tm_timestamp(text: str) -> dt.datetime | None:
    """
    Summary
    Parse a Time Machine timestamp string into an aware datetime.

    Inputs
    text: Timestamp string `YYYY-MM-DD-HHMMSS`.

    Outputs
    Timezone-aware datetime in local time, or None.

    Side effects
    None.

    Error handling
    Never raises; returns None on parse failures.

    Ties to other methods
    Used by `TimeMachineDiagnostics._fetch_uncached`.

    Why this exists
    Age calculations should be based on a normalized datetime representation.
    """
    try:
        if not text:
            return None
        naive = dt.datetime.strptime(text.strip(), "%Y-%m-%d-%H%M%S")
        local_tz = dt.datetime.now().astimezone().tzinfo
        return naive.replace(tzinfo=local_tz)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError):
        return None


def _age_days(value: dt.datetime) -> float:
    """
    Summary
    Compute the age in days from a timestamp to now.

    Inputs
    value: Timestamp datetime.

    Outputs
    Age in days as float.

    Side effects
    None.

    Error handling
    Never raises; returns 0.0 when computation fails.

    Ties to other methods
    Used by `TimeMachineDiagnostics._fetch_uncached`.

    Why this exists
    Backup recency thresholds are easier to express in days.
    """
    try:
        now = dt.datetime.now().astimezone()
        delta = now - value
        return max(0.0, float(delta.total_seconds()) / 86400.0)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError):
        return 0.0


def _tm_is_running(status_text: str) -> bool | None:
    """
    Summary
    Best-effort parse Time Machine running state from `tmutil status`.

    Inputs
    status_text: Command output.

    Outputs
    True/False when detected, else None.

    Side effects
    None.

    Error handling
    Never raises.

    Ties to other methods
    Used by `TimeMachineDiagnostics._fetch_uncached`.

    Why this exists
    It is useful to know when a backup is currently running while evaluating recency.
    """
    lowered = (status_text or "").lower()
    if not lowered.strip():
        return None
    if "running = 1" in lowered or "running = true" in lowered:
        return True
    if "running = 0" in lowered or "running = false" in lowered:
        return False
    return None
