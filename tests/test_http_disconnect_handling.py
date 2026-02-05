from __future__ import annotations

import errno
import unittest

from mac_health_checkup.app.backend.http.handler_factory import _is_client_disconnect

MODULE_PATH = "tests/test_http_disconnect_handling.py"


class HttpDisconnectHandlingTests(unittest.TestCase):
    """
    Summary
    Validate that the HTTP handler treats client disconnects as non-errors.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Relies on unittest assertions.

    Ties to other methods
    Tests `mac_health_checkup.app.backend.http.handler_factory._is_client_disconnect`.

    Why this exists
    Clients can cancel requests during refresh. The server should not treat broken pipes as internal errors or
    attempt to write a second response after disconnect.
    """

    def test_broken_pipe_is_detected(self) -> None:
        """
        Summary
        Ensure BrokenPipeError is treated as a disconnect.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Fails the test via assertions when the detector returns false.

        Ties to other methods
        Exercises the simplest disconnect exception type.

        Why this exists
        Broken pipes are normal when clients close connections mid-response.
        """

        self.assertTrue(_is_client_disconnect(BrokenPipeError()))

    def test_connection_reset_is_detected(self) -> None:
        """
        Summary
        Ensure ConnectionResetError is treated as a disconnect.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Fails the test via assertions when the detector returns false.

        Ties to other methods
        Exercises the common connection reset case.

        Why this exists
        Connection resets can happen when clients or proxies abort requests.
        """

        self.assertTrue(_is_client_disconnect(ConnectionResetError()))

    def test_oserror_errno_econnreset_is_detected(self) -> None:
        """
        Summary
        Ensure OSError errno ECONNRESET is treated as a disconnect.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Fails the test via assertions when the detector returns false.

        Ties to other methods
        Exercises errno-based disconnect detection.

        Why this exists
        Some socket write failures surface as plain OSError with an errno value.
        """

        exc = OSError(errno.ECONNRESET, "connection reset")
        self.assertTrue(_is_client_disconnect(exc))
