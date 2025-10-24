# diagnostics/logging_utils.py
import logging
from constants import DEBUG_LOG_PREFIX  # already exists

_def_log_configured = False


def configure_logging_once() -> None:
    global _def_log_configured
    if _def_log_configured:
        return

    root = logging.getLogger()
    if root.handlers:  # someone else already set it
        _def_log_configured = True
        return

    try:
        prefix = DEBUG_LOG_PREFIX
        fmt_prefix = (
            prefix.replace("{timestamp}", "%(asctime)s")
            .replace("{level}", "%(levelname)s")
            .replace("{context}", " %(name)s")
        )
        fmt = f"{fmt_prefix} %(message)s"
    except Exception:
        fmt = "[%(asctime)s %(levelname)s %(name)s] %(message)s"

    logging.basicConfig(level=logging.INFO, format=fmt)
    _def_log_configured = True


# run immediately so *every* sub-module gets a logger that works
configure_logging_once()
logger = logging.getLogger("diagnostics")
