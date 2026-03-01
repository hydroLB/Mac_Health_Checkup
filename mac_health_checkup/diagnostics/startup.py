from __future__ import annotations

from pathlib import Path

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils import safe_run
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/startup.py"


class StartupItemsDiagnostics:
    """
    Summary
    Collect launch agents and daemons from standard macOS launchd locations (read-only).

    Inputs
    None.

    Outputs
    Dict with lists of launch item labels grouped by scope.

    Side effects
    Reads filesystem directories and may execute `plutil` to extract labels.

    Error handling
    Returns `ok=false` when no sources are readable.

    Ties to other methods
    Used by the Startup section (`mac_health_checkup/app/gui/sections/startup.py`).

    Why this exists
    Startup items are a common cause of background CPU usage, network access, and unexpected behavior. Listing
    them read-only provides a strong troubleshooting signal.
    """

    _cache = Cache(get_config().timeouts.cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch launchd startup items with caching.

        Inputs
        None.

        Outputs
        Diagnostics dict with grouped item lists.

        Side effects
        Reads directories and runs bounded `plutil` calls when cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by Startup section refresh loops.

        Why this exists
        Startup item enumeration can be moderately expensive; caching keeps the UI responsive.
        """
        try:
            return cached_fetch(
                StartupItemsDiagnostics._cache, "startup_items", StartupItemsDiagnostics._fetch_uncached
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "StartupItemsDiagnostics.fetch", "Failed to fetch startup items", exc
                )
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch startup items without caching.

        Inputs
        None.

        Outputs
        Diagnostics dict.

        Side effects
        Reads filesystem and runs `plutil` to extract labels when possible.

        Error handling
        Never raises for missing directories; returns partial results.

        Ties to other methods
        Wrapped by `fetch` via `cached_fetch`.

        Why this exists
        Different machines may not have the same launchd directories; partial results are still useful.
        """
        logger = get_diagnostics_logger()
        context = new_context("StartupItemsDiagnostics")
        try:
            max_items = int(get_config().gui.startup_max_rows)
            timeout = int(get_config().timeouts.default_cmd_timeout)

            user_agents = _read_launch_items(Path.home() / "Library" / "LaunchAgents", timeout=timeout)
            system_agents = _read_launch_items(Path("/Library/LaunchAgents"), timeout=timeout)
            system_daemons = _read_launch_items(Path("/Library/LaunchDaemons"), timeout=timeout)

            ok_any = bool(user_agents or system_agents or system_daemons)
            if not ok_any:
                logger.info(
                    "no launch items found",
                    event="startup_empty",
                    context=context,
                    payload={},
                )

            return {
                "ok": ok_any,
                "user_agents": user_agents[:max_items],
                "system_agents": system_agents[:max_items],
                "system_daemons": system_daemons[:max_items],
            }
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError) as exc:
            logger.warning(
                "startup item enumeration failed",
                event="startup_error",
                context=context,
                payload={"error": str(exc), "error_type": type(exc).__name__},
            )
            return {
                "ok": False,
                "error": format_error(
                    MODULE_PATH,
                    "StartupItemsDiagnostics._fetch_uncached",
                    "Failed to collect startup items",
                    exc,
                ),
            }


def _read_launch_items(directory: Path, *, timeout: int) -> list[str]:
    """
    Summary
    Read launchd plist labels from a directory.

    Inputs
    directory: Path to the LaunchAgents/LaunchDaemons directory.
    timeout: Command timeout seconds for label extraction.

    Outputs
    Sorted list of labels or filenames.

    Side effects
    Reads directory listing and may execute `plutil`.

    Error handling
    Never raises for missing directories; returns an empty list.

    Ties to other methods
    Used by `StartupItemsDiagnostics._fetch_uncached`.

    Why this exists
    Directory walking should be isolated so the collector stays small and testable.
    """
    try:
        if not directory.is_dir():
            return []
        items: list[str] = []
        for path in sorted(directory.glob("*.plist")):
            label = _best_effort_plist_label(path, timeout=timeout)
            items.append(label)
        return sorted({item for item in items if item.strip()}, key=lambda v: v.lower())
    except OSError:
        return []
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_read_launch_items", "Failed to read launch items", exc)
        ) from exc


def _best_effort_plist_label(path: Path, *, timeout: int) -> str:
    """
    Summary
    Extract the `Label` field from a launchd plist, falling back to filename.

    Inputs
    path: Plist path.
    timeout: `plutil` timeout seconds.

    Outputs
    Label string.

    Side effects
    Executes `plutil` as a subprocess when available.

    Error handling
    Returns filename on extraction failure.

    Ties to other methods
    Used by `_read_launch_items`.

    Why this exists
    Labels are more meaningful than filenames and often encode vendor identifiers.
    """
    try:
        out, _err = safe_run(
            ["plutil", "-extract", "Label", "raw", "-o", "-", str(path)],
            context="plutil_label",
            allow_sudo=False,
            timeout=max(1, int(timeout)),
        )
        label = (out or "").strip()
        if label:
            return label
        return path.stem
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError):
        return path.stem
