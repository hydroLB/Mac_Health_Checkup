from __future__ import annotations

import threading
import unittest

from mac_health_checkup.core.config.public import get_config, reset_config_cache

MODULE_PATH = "tests/test_config_thread_safety.py"


class ConfigThreadSafetyTests(unittest.TestCase):
    """
    Summary
    Validate that config caching remains safe under concurrent access.

    Inputs
    None.

    Outputs
    None.

    Side effects
    Invokes `get_config` from multiple threads.

    Error handling
    Relies on unittest assertions.

    Ties to other methods
    Exercises `mac_health_checkup.core.config.public.get_config` and `reset_config_cache`.

    Why this exists
    The snapshot API uses `ThreadingHTTPServer`, and UI refresh loops can also read config concurrently. The
    config cache must never throw due to races.
    """

    def test_get_config_concurrent_calls_do_not_raise(self) -> None:
        """
        Summary
        Ensure concurrent `get_config` calls do not raise exceptions.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Spawns threads that call `get_config`.

        Error handling
        Fails the test via assertions when any worker captures an exception.

        Ties to other methods
        Calls `reset_config_cache` to ensure the test exercises the cache fill path.

        Why this exists
        A race during cache initialization can crash request threads and destabilize the agent server.
        """

        reset_config_cache()
        errors: list[BaseException] = []
        errors_lock = threading.Lock()

        def _worker() -> None:
            try:
                _ = get_config()
            except BaseException as exc:  # noqa: BLE001
                with errors_lock:
                    errors.append(exc)

        threads = [threading.Thread(target=_worker, name=f"cfg-{i}") for i in range(40)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2.0)

        self.assertEqual(errors, [], f"{MODULE_PATH}: unexpected errors: {errors!r}")
