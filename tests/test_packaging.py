from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import venv
import zipfile
from email.parser import Parser
from pathlib import Path
from typing import cast

from mac_health_checkup.core.types import JsonDict

MODULE_PATH = "tests/test_packaging.py"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_command(argv: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """
    Summary
    Run a bounded subprocess with captured text output for packaging assertions.

    Inputs
    argv: Command and arguments to execute.
    cwd: Working directory for the child process.
    env: Explicit child-process environment.

    Outputs
    Completed subprocess result without raising for a non-zero exit.

    Side effects
    Starts a local subprocess that may write only within pytest temporary directories.

    Error handling
    Raises `TimeoutExpired` when a packaging command exceeds two minutes.

    Ties to other methods
    Used by `test_distribution_build_install_and_console_script` for build, install, and runtime probes.

    Why this exists
    Captured output makes an offline build or installation failure actionable in CI.
    """
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_config_sync_make_contract(tmp_path: Path) -> None:
    """
    Summary
    Verify the explicit Make targets detect and repair a stale packaged default config.

    Inputs
    Pytest temporary directory and the repository Makefile.

    Outputs
    Assertions on matching, stale, synchronized, and rechecked config copies.

    Side effects
    Writes disposable config files and invokes local Make targets under `tmp_path`.

    Error handling
    Raises `AssertionError` with captured Make output when the synchronization contract regresses.

    Ties to other methods
    Exercises the `config-sync` and `config-sync-check` targets used by `check-python`.

    Why this exists
    Contributors need one discoverable update command and CI must fail when package data drifts from its source.
    """
    source_config = tmp_path / "config.json"
    packaged_config = tmp_path / "default_config.json"
    source_config.write_text('{"network": {"capacity_test_enabled": false}}\n', encoding="utf-8")
    shutil.copy2(source_config, packaged_config)
    make_command = [
        "make",
        "-f",
        str(REPO_ROOT / "Makefile"),
        f"CONFIG_SOURCE={source_config}",
        f"PACKAGED_CONFIG={packaged_config}",
    ]
    environment = dict(os.environ)

    matching_result = _run_command([*make_command, "config-sync-check"], cwd=tmp_path, env=environment)
    assert matching_result.returncode == 0, matching_result.stdout + matching_result.stderr

    packaged_config.write_text("{}\n", encoding="utf-8")
    stale_result = _run_command([*make_command, "config-sync-check"], cwd=tmp_path, env=environment)
    assert stale_result.returncode != 0
    assert "Run 'make config-sync'." in stale_result.stderr

    sync_result = _run_command([*make_command, "config-sync"], cwd=tmp_path, env=environment)
    assert sync_result.returncode == 0, sync_result.stdout + sync_result.stderr
    assert packaged_config.read_bytes() == source_config.read_bytes()

    recheck_result = _run_command([*make_command, "config-sync-check"], cwd=tmp_path, env=environment)
    assert recheck_result.returncode == 0, recheck_result.stdout + recheck_result.stderr


def test_distribution_build_install_and_console_script(tmp_path: Path) -> None:
    """
    Summary
    Build, inspect, install, and execute the Python distributions without network access.

    Inputs
    Pytest temporary directory and the repository's packaging sources.

    Outputs
    Assertions on distributions, metadata, secure config precedence, installation, and console help.

    Side effects
    Copies packaging sources, builds artifacts, and creates an isolated virtual environment under `tmp_path`.

    Error handling
    Raises `AssertionError` with captured subprocess output when build, install, or execution fails.

    Ties to other methods
    Exercises setuptools discovery, package data, `resolve_config_path`, `get_config`, and the console entrypoint.

    Why this exists
    A source checkout can hide missing package files; this regression proves the published artifacts work alone.
    """
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    for filename in (
        ".mac-health-checkup-source",
        "LICENSE",
        "Makefile",
        "README.md",
        "pyproject.toml",
    ):
        shutil.copy2(REPO_ROOT / filename, source_dir / filename)
    shutil.copytree(
        REPO_ROOT / "mac_health_checkup",
        source_dir / "mac_health_checkup",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    excluded_package = source_dir / "unrelated_package"
    excluded_package.mkdir()
    (excluded_package / "__init__.py").write_text(
        'raise RuntimeError("unrelated package must not ship")\n', encoding="utf-8"
    )
    checkout_config = cast(
        JsonDict,
        json.loads((REPO_ROOT / "config" / "config.json").read_text(encoding="utf-8")),
    )
    checkout_config_dir = source_dir / "config"
    checkout_config_dir.mkdir()
    checkout_config_path = checkout_config_dir / "config.json"
    shutil.copy2(REPO_ROOT / "config" / "config.json", checkout_config_path)

    # Copied/installed package probes validate artifacts, but must not pollute checkout coverage paths.
    environment = {
        key: value
        for key, value in os.environ.items()
        if key != "PYTHONPATH"
        and not key.startswith("COV_CORE_")
        and not key.startswith("MAC_HEALTH_CHECKUP_")
    }
    environment.update(
        {
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    dist_dir = tmp_path / "dist"
    build_result = _run_command(
        [
            "make",
            "-f",
            str(source_dir / "Makefile"),
            f"PYTHON={sys.executable}",
            f"DIST_DIR={dist_dir}",
            "build",
        ],
        cwd=source_dir,
        env=environment,
    )
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr
    assert "Package would be ignored" not in build_result.stdout + build_result.stderr

    wheels = tuple(dist_dir.glob("*.whl"))
    sdists = tuple(dist_dir.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1

    with zipfile.ZipFile(wheels[0]) as wheel_archive:
        wheel_names = set(wheel_archive.namelist())
        dist_info_roots = {
            name.split("/", maxsplit=1)[0]
            for name in wheel_names
            if name.split("/", maxsplit=1)[0].endswith(".dist-info")
        }
        assert len(dist_info_roots) == 1
        assert {name.split("/", maxsplit=1)[0] for name in wheel_names} == {
            "mac_health_checkup",
            *dist_info_roots,
        }
        assert "mac_health_checkup/resources/default_config.json" in wheel_names
        assert ".mac-health-checkup-source" not in wheel_names
        assert not any(name.startswith("unrelated_package/") for name in wheel_names)
        assert not any(name.startswith(("config/", "docs/", "tests/", "tools/")) for name in wheel_names)

        metadata_name = next(name for name in wheel_names if name.endswith(".dist-info/METADATA"))
        entry_points_name = next(name for name in wheel_names if name.endswith(".dist-info/entry_points.txt"))
        top_level_name = next(name for name in wheel_names if name.endswith(".dist-info/top_level.txt"))
        metadata = Parser().parsestr(wheel_archive.read(metadata_name).decode("utf-8"))
        assert metadata.get("Name") == "mac-health-checkup"
        assert metadata.get("Version") == "0.2.0"
        assert metadata.get("Requires-Python") == ">=3.11"
        assert metadata.get("License-Expression") == "MIT"
        assert metadata.get_all("Requires-Dist") is None
        assert any(name.endswith(".dist-info/licenses/LICENSE") for name in wheel_names)
        assert wheel_archive.read(entry_points_name).decode("utf-8").strip() == (
            "[console_scripts]\nmac-health-checkup = mac_health_checkup.app.entrypoint:main"
        )
        assert wheel_archive.read(top_level_name).decode("utf-8").strip() == "mac_health_checkup"
        assert (
            wheel_archive.read("mac_health_checkup/resources/default_config.json")
            == (REPO_ROOT / "config" / "config.json").read_bytes()
        )

    with tarfile.open(sdists[0], mode="r:gz") as sdist_archive:
        sdist_names = set(sdist_archive.getnames())
    assert any(name.endswith("/pyproject.toml") for name in sdist_names)
    assert any(name.endswith("/mac_health_checkup/resources/default_config.json") for name in sdist_names)
    assert not any("/unrelated_package/" in name for name in sdist_names)
    sdist_roots = {name.split("/", maxsplit=1)[0] for name in sdist_names}
    assert len(sdist_roots) == 1
    assert f"{next(iter(sdist_roots))}/.mac-health-checkup-source" not in sdist_names
    assert f"{next(iter(sdist_roots))}/config/config.json" not in sdist_names

    install_dir = tmp_path / "installed"
    venv.EnvBuilder(with_pip=True).create(install_dir)
    scripts_dir = install_dir / ("Scripts" if os.name == "nt" else "bin")
    python_executable = scripts_dir / ("python.exe" if os.name == "nt" else "python")
    install_result = _run_command(
        [
            str(python_executable),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            "--no-index",
            str(wheels[0]),
        ],
        cwd=tmp_path,
        env=environment,
    )
    assert install_result.returncode == 0, install_result.stdout + install_result.stderr

    outside_repo = tmp_path / "outside-repository"
    outside_repo.mkdir()
    console_script = scripts_dir / ("mac-health-checkup.exe" if os.name == "nt" else "mac-health-checkup")
    help_result = _run_command([str(console_script), "--help"], cwd=outside_repo, env=environment)
    assert help_result.returncode == 0, help_result.stdout + help_result.stderr
    assert "Run Mac Health Checkup." in help_result.stdout

    probe = (
        "import json; "
        "from mac_health_checkup.core.config import get_config; "
        "from mac_health_checkup.core.config.io import resolve_config_path; "
        "config = get_config(); "
        "print(json.dumps({"
        "'capacity_test_enabled': config.network.capacity_test_enabled, "
        "'capacity_test_cache_ttl': config.network.capacity_test_cache_ttl, "
        "'config_path': str(resolve_config_path())}))"
    )
    packaged_config_result = _run_command(
        [str(python_executable), "-c", probe], cwd=outside_repo, env=environment
    )
    assert packaged_config_result.returncode == 0, (
        packaged_config_result.stdout + packaged_config_result.stderr
    )
    packaged_config = cast(JsonDict, json.loads(packaged_config_result.stdout))
    assert packaged_config["capacity_test_enabled"] is False
    assert packaged_config["capacity_test_cache_ttl"] == 3600
    packaged_config_path = packaged_config["config_path"]
    assert isinstance(packaged_config_path, str)
    assert Path(packaged_config_path).is_relative_to(install_dir)

    checkout_network = checkout_config.get("network")
    assert isinstance(checkout_network, dict)
    checkout_network["capacity_test_enabled"] = True
    checkout_config_path.write_text(json.dumps(checkout_config), encoding="utf-8")

    installed_site_packages = Path(packaged_config_path).parents[2]
    sibling_config_dir = installed_site_packages / "config"
    sibling_config_dir.mkdir()
    (sibling_config_dir / "config.json").write_text(json.dumps(checkout_config), encoding="utf-8")
    sibling_config_result = _run_command(
        [str(python_executable), "-c", probe], cwd=outside_repo, env=environment
    )
    assert sibling_config_result.returncode == 0, sibling_config_result.stdout + sibling_config_result.stderr
    sibling_config_probe = cast(JsonDict, json.loads(sibling_config_result.stdout))
    assert sibling_config_probe["capacity_test_enabled"] is False
    assert sibling_config_probe["config_path"] == packaged_config_path

    caller_config_dir = outside_repo / "config"
    caller_config_dir.mkdir()
    (caller_config_dir / "config.json").write_text(json.dumps(checkout_config), encoding="utf-8")
    caller_config_result = _run_command(
        [str(python_executable), "-c", probe], cwd=outside_repo, env=environment
    )
    assert caller_config_result.returncode == 0, caller_config_result.stdout + caller_config_result.stderr
    caller_config_probe = cast(JsonDict, json.loads(caller_config_result.stdout))
    assert caller_config_probe["capacity_test_enabled"] is False
    assert caller_config_probe["config_path"] == packaged_config_path

    checkout_environment = dict(environment)
    checkout_environment["PYTHONPATH"] = str(source_dir)
    checkout_config_result = _run_command(
        [sys.executable, "-c", probe], cwd=outside_repo, env=checkout_environment
    )
    assert checkout_config_result.returncode == 0, (
        checkout_config_result.stdout + checkout_config_result.stderr
    )
    checkout_config_probe = cast(JsonDict, json.loads(checkout_config_result.stdout))
    assert checkout_config_probe["capacity_test_enabled"] is True
    resolved_checkout_path = checkout_config_probe["config_path"]
    assert isinstance(resolved_checkout_path, str)
    assert Path(resolved_checkout_path) == checkout_config_path
