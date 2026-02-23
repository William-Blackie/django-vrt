from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAKE = shutil.which("make")
ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

pytestmark = pytest.mark.skipif(MAKE is None, reason="make is required")


def _run_make(*args: str) -> subprocess.CompletedProcess[str]:
    assert MAKE is not None
    return subprocess.run(
        [MAKE, *args],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_make_help_lists_core_targets() -> None:
    result = _run_make("help")
    assert result.returncode == 0, result.stderr
    help_output = ANSI_ESCAPE.sub("", result.stdout)

    for target in (
        "venv",
        "bootstrap",
        "install",
        "dev-install",
        "lint",
        "type-check",
        "coverage",
        "check",
        "test",
        "test-lf",
        "build",
        "clean",
        "release",
    ):
        assert re.search(rf"^\s*{re.escape(target)}\s+", help_output, flags=re.MULTILINE), help_output


def test_make_release_requires_version() -> None:
    result = _run_make("-n", "release")
    assert result.returncode != 0
    assert "VERSION is required" in result.stderr


@pytest.mark.parametrize(
    "args",
    [
        ("-n", "venv"),
        ("-n", "bootstrap"),
        ("-n", "install"),
        ("-n", "dev-install"),
        ("-n", "lint"),
        ("-n", "type-check"),
        ("-n", "coverage"),
        ("-n", "test"),
        ("-n", "test-lf"),
        ("-n", "build"),
        ("-n", "check"),
        ("-n", "clean"),
        ("-n", "VERSION=0.0.0", "release"),
    ],
)
def test_make_targets_are_invokable_in_dry_run(args: tuple[str, ...]) -> None:
    result = _run_make(*args)
    assert result.returncode == 0, f"{' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
