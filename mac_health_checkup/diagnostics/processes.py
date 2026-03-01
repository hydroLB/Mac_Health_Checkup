from __future__ import annotations

from dataclasses import dataclass

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import safe_float, safe_int
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils import safe_run
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/processes.py"


@dataclass(frozen=True)
class ProcessRow:
    """
    Summary
    Represent a single process row from `ps` output.

    Inputs
    pid: Process id.
    cpu_percent: CPU percent.
    mem_percent: Memory percent.
    command: Command name.

    Outputs
    Immutable process row.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by `_parse_ps_rows` and emitted by `TopProcessesDiagnostics`.

    Why this exists
    Keeping process rows strongly typed avoids brittle indexing and helps keep output deterministic.
    """

    pid: int
    cpu_percent: float
    mem_percent: float
    command: str


class TopProcessesDiagnostics:
    """
    Summary
    Collect top process offenders by CPU and memory usage (read-only).

    Inputs
    None.

    Outputs
    Dict with `top_cpu` and `top_mem` lists.

    Side effects
    Executes `ps` commands.

    Error handling
    Returns `ok=false` when no process rows can be parsed.

    Ties to other methods
    Used by the Processes section (`mac_health_checkup/app/gui/sections/processes.py`).

    Why this exists
    High CPU or memory consumers are often the most actionable explanation for performance symptoms.
    """

    _cache = Cache(get_config().timeouts.cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch top processes with caching.

        Inputs
        None.

        Outputs
        Diagnostics dict with lists of process rows.

        Side effects
        Executes `ps` when cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by the Processes section refresh loop.

        Why this exists
        Process lists can be noisy and expensive to refresh at high frequency; caching keeps the UI stable.
        """
        try:
            return cached_fetch(
                TopProcessesDiagnostics._cache, "top_processes", TopProcessesDiagnostics._fetch_uncached
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "TopProcessesDiagnostics.fetch", "Failed to fetch processes", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch top processes without caching.

        Inputs
        None.

        Outputs
        Diagnostics dict.

        Side effects
        Executes `ps`.

        Error handling
        Never raises for command failures; returns partial results when possible.

        Ties to other methods
        Wrapped by `fetch` via `cached_fetch`.

        Why this exists
        `ps` behavior can vary across environments; failures should not abort the overall dashboard.
        """
        logger = get_diagnostics_logger()
        context = new_context("TopProcessesDiagnostics")
        try:
            timeout = int(get_config().timeouts.default_cmd_timeout)
            max_rows = int(get_config().gui.processes_max_rows)

            cpu_out, cpu_err = safe_run(
                ["ps", "-Ao", "pid,pcpu,pmem,comm", "-r"],
                context="ps_top_cpu",
                allow_sudo=False,
                timeout=timeout,
            )
            mem_out, mem_err = safe_run(
                ["ps", "-Ao", "pid,pcpu,pmem,comm", "-m"],
                context="ps_top_mem",
                allow_sudo=False,
                timeout=timeout,
            )
            top_cpu = _parse_ps_rows(cpu_out or "", limit=max_rows)
            top_mem = _parse_ps_rows(mem_out or "", limit=max_rows)

            ok_any = bool(top_cpu or top_mem)
            if not ok_any:
                logger.info(
                    "ps output empty",
                    event="processes_empty",
                    context=context,
                    payload={"cpu_error": cpu_err or "", "mem_error": mem_err or ""},
                )
            return {
                "ok": ok_any,
                "top_cpu": [row.__dict__ for row in top_cpu],
                "top_mem": [row.__dict__ for row in top_mem],
                "raw_cpu": cpu_out or "",
                "raw_mem": mem_out or "",
            }
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError) as exc:
            logger.warning(
                "process collection failed",
                event="processes_error",
                context=context,
                payload={"error": str(exc), "error_type": type(exc).__name__},
            )
            return {
                "ok": False,
                "error": format_error(
                    MODULE_PATH,
                    "TopProcessesDiagnostics._fetch_uncached",
                    "Failed to collect processes",
                    exc,
                ),
            }


def _parse_ps_rows(text: str, *, limit: int) -> list[ProcessRow]:
    """
    Summary
    Parse `ps -Ao pid,pcpu,pmem,comm` output into structured rows.

    Inputs
    text: Raw ps output.
    limit: Max number of rows to return.

    Outputs
    List of ProcessRow values.

    Side effects
    None.

    Error handling
    Never raises; returns an empty list on malformed input.

    Ties to other methods
    Used by `TopProcessesDiagnostics._fetch_uncached`.

    Why this exists
    `ps` output is untyped text and includes a header row; parsing must be robust and conservative.
    """
    if limit <= 0:
        return []
    lines = [line.rstrip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return []
    # Drop header if present.
    if "pid" in lines[0].lower() and "pcpu" in lines[0].lower():
        lines = lines[1:]
    out: list[ProcessRow] = []
    for line in lines:
        # ps columns are whitespace-separated, but command may contain spaces on some builds.
        parts = [p for p in line.split() if p]
        if len(parts) < 4:
            continue
        pid = safe_int(parts[0])
        cpu = safe_float(parts[1])
        mem = safe_float(parts[2])
        command = " ".join(parts[3:]).strip()
        if pid is None or cpu is None or mem is None or not command:
            continue
        out.append(ProcessRow(pid=int(pid), cpu_percent=float(cpu), mem_percent=float(mem), command=command))
        if len(out) >= limit:
            break
    return out
