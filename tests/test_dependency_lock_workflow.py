from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

MODULE_PATH = "tests/test_dependency_lock_workflow.py"
REPO_ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = REPO_ROOT / "Makefile"


@dataclass(frozen=True)
class LockWorkflowHarness:
    """Paths for a temporary dependency-lock workflow driven by a fake Python executable."""

    repo_root: Path
    generated_dir: Path
    invocation_log: Path
    output_log: Path
    bootstrap_python: Path
    lock_venv: Path
    lock_python: Path


def _run_command(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """
    Summary
    Run a text-mode subprocess for the temporary Makefile harness.

    Inputs
    argv: Command arguments to execute.
    cwd: Working directory for the command.
    env: Optional environment override.
    check: Whether a non-zero exit should raise `CalledProcessError`.

    Outputs
    Completed subprocess result with captured text output.

    Side effects
    Starts a local subprocess and may mutate only the caller-provided temporary directory.

    Error handling
    Raises `CalledProcessError` when `check` is true and the command fails.

    Ties to other methods
    Used by the Git setup helper and dependency-check workflow tests.

    Why this exists
    Centralized subprocess settings keep the Makefile contract tests deterministic and easy to diagnose.
    """
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """
    Summary
    Run a Git command in the disposable repository.

    Inputs
    repo_root: Temporary Git repository root.
    args: Git subcommand and arguments.

    Outputs
    Completed Git subprocess result.

    Side effects
    Reads or updates only the temporary repository passed by the test.

    Error handling
    Raises `CalledProcessError` when Git rejects the requested operation.

    Ties to other methods
    Used by `_create_harness` and the dirty-worktree assertions.

    Why this exists
    The regression requires a real Git index so it can prove `deps-check` no longer compares against that index.
    """
    return _run_command(["git", *args], cwd=repo_root)


def _write_fake_python(path: Path) -> None:
    """
    Summary
    Create a fake Python executable that emulates version checks, venv creation, pip, and pip-tools compilation.

    Inputs
    path: Destination for the executable shim.

    Outputs
    None.

    Side effects
    Writes one executable file under the pytest temporary directory.

    Error handling
    Propagates filesystem errors to the test.

    Ties to other methods
    Used by `_create_harness` to exercise the real Makefile without installing dependencies.

    Why this exists
    Lock workflow tests need deterministic generated files and must never access a package index.
    """
    script = f"#!{sys.executable}\n" + textwrap.dedent(
        """
        from pathlib import Path
        import os
        import shutil
        import sys

        args = sys.argv[1:]
        invocation_log = Path(os.environ["FAKE_LOCK_INVOCATION_LOG"])
        with invocation_log.open("a", encoding="utf-8") as stream:
            stream.write("\\t".join(args) + "\\n")

        if args and args[0] == "-c":
            code = args[1] if len(args) > 1 else ""
            print("3.11" if "[:2]" in code else "3.11.15")
            raise SystemExit(0)

        if args[:2] == ["-m", "venv"]:
            destination = Path(args[2]) / "bin" / "python"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(__file__), destination)
            destination.chmod(0o755)
            raise SystemExit(0)

        if args[:3] == ["-m", "pip", "install"]:
            raise SystemExit(0)

        if args[:3] == ["-m", "piptools", "compile"]:
            output_path = Path(args[args.index("--output-file") + 1])
            input_path = Path(args[-1])
            generated_path = Path(os.environ["FAKE_LOCK_GENERATED_DIR"]) / (
                input_path.stem + ".txt"
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(generated_path, output_path)
            output_log = Path(os.environ["FAKE_LOCK_OUTPUT_LOG"])
            with output_log.open("a", encoding="utf-8") as stream:
                stream.write(str(output_path) + "\\n")
            raise SystemExit(0)

        raise SystemExit("unexpected fake Python invocation: " + repr(args))
        """
    )
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def _create_harness(tmp_path: Path) -> LockWorkflowHarness:
    """
    Summary
    Build a temporary Git repository and fake lock toolchain for Makefile contract tests.

    Inputs
    tmp_path: Pytest-provided temporary directory.

    Outputs
    `LockWorkflowHarness` containing all temporary workflow paths.

    Side effects
    Creates temporary files, initializes a Git repository, and records one local commit.

    Error handling
    Propagates filesystem or subprocess failures to the test.

    Ties to other methods
    Used by each dependency lock workflow regression test.

    Why this exists
    A disposable committed baseline makes matching and stale dirty-lock scenarios reproducible without touching the
    shared worktree.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "requirements.in").write_text("# runtime input\n", encoding="utf-8")
    (repo_root / "requirements-dev.in").write_text(
        "-r requirements.in\n\nexample-tool==1\n", encoding="utf-8"
    )
    (repo_root / "requirements.txt").write_text("runtime-lock-v1\n", encoding="utf-8")
    (repo_root / "requirements-dev.txt").write_text("dev-lock-v1\n", encoding="utf-8")

    _git(repo_root, "init", "--quiet")
    _git(
        repo_root, "add", "requirements.in", "requirements-dev.in", "requirements.txt", "requirements-dev.txt"
    )
    _run_command(
        [
            "git",
            "-c",
            "user.name=Lock Workflow Test",
            "-c",
            "user.email=lock-workflow@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "initial lockfiles",
        ],
        cwd=repo_root,
    )

    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    (generated_dir / "requirements.txt").write_text("runtime-lock-v1\n", encoding="utf-8")
    (generated_dir / "requirements-dev.txt").write_text("dev-lock-v1\n", encoding="utf-8")

    bootstrap_python = tmp_path / "fake-python"
    _write_fake_python(bootstrap_python)
    lock_venv = tmp_path / "lock-venv"
    lock_python = lock_venv / "bin" / "python"
    lock_python.parent.mkdir(parents=True)
    shutil.copyfile(bootstrap_python, lock_python)
    lock_python.chmod(0o755)

    return LockWorkflowHarness(
        repo_root=repo_root,
        generated_dir=generated_dir,
        invocation_log=tmp_path / "invocations.log",
        output_log=tmp_path / "outputs.log",
        bootstrap_python=bootstrap_python,
        lock_venv=lock_venv,
        lock_python=lock_python,
    )


def _run_deps_check(harness: LockWorkflowHarness) -> subprocess.CompletedProcess[str]:
    """
    Summary
    Run the repository Makefile's `deps-check` target against the fake toolchain.

    Inputs
    harness: Temporary repository and toolchain paths.

    Outputs
    Completed Make subprocess result without raising for a stale-lock exit.

    Side effects
    Invokes Make and writes fake-tool logs under the pytest temporary directory.

    Error handling
    Returns non-zero Make results to the caller for explicit assertions.

    Ties to other methods
    Used by all dependency lock workflow tests.

    Why this exists
    Every regression should exercise the production Makefile recipe while package installation remains stubbed out.
    """
    env = dict(os.environ)
    env.update(
        {
            "FAKE_LOCK_GENERATED_DIR": str(harness.generated_dir),
            "FAKE_LOCK_INVOCATION_LOG": str(harness.invocation_log),
            "FAKE_LOCK_OUTPUT_LOG": str(harness.output_log),
        }
    )
    return _run_command(
        [
            "make",
            "-f",
            str(MAKEFILE),
            "deps-check",
            f"PYTHON_BOOTSTRAP={harness.bootstrap_python}",
            f"LOCK_VENV={harness.lock_venv}",
            f"LOCK_PYTHON={harness.lock_python}",
            "PYTHON_VERSION=3.11.15",
            "PYTHON_SERIES=3.11",
        ],
        cwd=harness.repo_root,
        env=env,
        check=False,
    )


def _assert_temporary_outputs_were_removed(harness: LockWorkflowHarness) -> None:
    """
    Summary
    Verify pip-tools wrote only temporary comparison outputs and the Makefile cleanup trap removed them.

    Inputs
    harness: Temporary workflow paths including the fake compiler output log.

    Outputs
    Assertions only.

    Side effects
    Reads the fake compiler output log.

    Error handling
    Raises `AssertionError` when outputs targeted the worktree or survived cleanup.

    Ties to other methods
    Used by the matching and stale lockfile tests.

    Why this exists
    Exit status alone cannot prove the verification target preserved the developer's working lockfiles.
    """
    compiled_paths = tuple(
        Path(line) for line in harness.output_log.read_text(encoding="utf-8").splitlines() if line
    )
    assert len(compiled_paths) == 2
    assert all(path.parent != harness.repo_root for path in compiled_paths)
    assert all(not path.exists() for path in compiled_paths)


def test_deps_check_accepts_matching_dirty_lockfiles_without_mutation(tmp_path: Path) -> None:
    """
    Summary
    Verify matching uncommitted dependency inputs and lockfiles pass without being rewritten.

    Inputs
    tmp_path: Pytest-provided temporary directory.

    Outputs
    Assertions on exit status, Git dirty state, file bytes, and temporary cleanup.

    Side effects
    Runs the fake dependency verifier inside a disposable Git repository.

    Error handling
    Raises `AssertionError` if `deps-check` relies on the Git index or mutates working lockfiles.

    Ties to other methods
    Exercises the `deps-check` Makefile target through `_run_deps_check`.

    Why this exists
    Developers must be able to validate a correct dependency update before staging it.
    """
    harness = _create_harness(tmp_path)
    (harness.repo_root / "requirements-dev.in").write_text(
        "-r requirements.in\n\nexample-tool==2\n", encoding="utf-8"
    )
    (harness.repo_root / "requirements-dev.txt").write_text("dev-lock-v2\n", encoding="utf-8")
    (harness.generated_dir / "requirements-dev.txt").write_text("dev-lock-v2\n", encoding="utf-8")
    before = {
        name: (harness.repo_root / name).read_bytes() for name in ("requirements.txt", "requirements-dev.txt")
    }
    dirty_before = _git(harness.repo_root, "diff", "--name-only").stdout.splitlines()
    assert dirty_before == ["requirements-dev.in", "requirements-dev.txt"]

    completed = _run_deps_check(harness)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert {
        name: (harness.repo_root / name).read_bytes() for name in ("requirements.txt", "requirements-dev.txt")
    } == before
    assert _git(harness.repo_root, "diff", "--name-only").stdout.splitlines() == dirty_before
    _assert_temporary_outputs_were_removed(harness)


def test_deps_check_rejects_stale_lockfiles_without_mutation(tmp_path: Path) -> None:
    """
    Summary
    Verify a stale working lockfile fails validation without being regenerated in place.

    Inputs
    tmp_path: Pytest-provided temporary directory.

    Outputs
    Assertions on failure output, preserved bytes, Git state, and temporary cleanup.

    Side effects
    Runs the fake dependency verifier inside a disposable Git repository.

    Error handling
    Raises `AssertionError` if a stale lock passes or the check rewrites it.

    Ties to other methods
    Exercises the `deps-check` Makefile target through `_run_deps_check`.

    Why this exists
    A check target should diagnose stale generated artifacts while leaving explicit regeneration to `deps-lock`.
    """
    harness = _create_harness(tmp_path)
    (harness.repo_root / "requirements-dev.in").write_text(
        "-r requirements.in\n\nexample-tool==2\n", encoding="utf-8"
    )
    (harness.generated_dir / "requirements-dev.txt").write_text("dev-lock-v2\n", encoding="utf-8")
    before = (harness.repo_root / "requirements-dev.txt").read_bytes()
    dirty_before = _git(harness.repo_root, "diff", "--name-only").stdout.splitlines()
    assert dirty_before == ["requirements-dev.in"]

    completed = _run_deps_check(harness)

    assert completed.returncode != 0
    assert "requirements-dev.txt is out of date" in completed.stderr
    assert "make deps-lock" in completed.stderr
    assert (harness.repo_root / "requirements-dev.txt").read_bytes() == before
    assert _git(harness.repo_root, "diff", "--name-only").stdout.splitlines() == dirty_before
    _assert_temporary_outputs_were_removed(harness)


def test_deps_check_reuses_lock_environment_across_supported_patch_versions(tmp_path: Path) -> None:
    """
    Summary
    Verify a Python 3.11.15 lock environment is reused when it matches the preferred patch pin.

    Inputs
    tmp_path: Pytest-provided temporary directory.

    Outputs
    Assertions on successful verification and fake toolchain invocation history.

    Side effects
    Runs the fake dependency verifier inside a disposable repository.

    Error handling
    Raises `AssertionError` if the compatible lock environment is deleted and recreated.

    Ties to other methods
    Exercises the series-based lock environment guard in the `deps-bootstrap` Makefile target.

    Why this exists
    Supported patch releases must not trigger a perpetual rebuild of `.venv-lock` on every check.
    """
    harness = _create_harness(tmp_path)

    completed = _run_deps_check(harness)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    invocations = tuple(
        tuple(line.split("\t"))
        for line in harness.invocation_log.read_text(encoding="utf-8").splitlines()
        if line
    )
    assert not any(arguments[:2] == ("-m", "venv") for arguments in invocations)
