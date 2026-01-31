from mac_health_checkup.core.utils.shell import safe_run

MODULE_PATH = "tests/test_shell_integration.py"


def test_safe_run_echo() -> None:
    """
    Purpose: Validate safe_run executes a simple command successfully.
    Ties: Exercises shell utilities against a deterministic command.
    Inputs: No external inputs beyond the echo command.
    Outputs: Assertions on stdout and error handling.
    Side effects: Executes a subprocess.
    Why: Confirms the shell boundary returns output without errors.
    """
    try:
        out, err = safe_run(["/bin/echo", "hello"], context="test_safe_run_echo", allow_sudo=False, timeout=2)
        assert err is None
        assert out is not None
        assert out.strip() == "hello"
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
        raise AssertionError(f"{MODULE_PATH}:test_safe_run_echo failed: {exc}") from exc
