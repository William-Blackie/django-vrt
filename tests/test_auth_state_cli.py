from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

import djvrt.auth_state


def test_auth_state_cli_parse_args_defaults() -> None:
    from djvrt.auth_state_cli import parse_args

    args = parse_args(["--email", "u@example.test", "--password", "secret"])
    assert args.base_url == "http://localhost:8000"
    assert args.wait_until == "domcontentloaded"


def test_auth_state_cli_main_calls_create_form_auth_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from djvrt.auth_state_cli import main as auth_state_main

    output = tmp_path / "state.json"

    def fake_create_form_auth_state(**kwargs: object) -> Path:
        assert kwargs["email"] == "u@example.test"
        assert kwargs["password"] == "secret"
        return output

    monkeypatch.setattr("djvrt.auth_state_cli.create_form_auth_state", fake_create_form_auth_state)

    rc = auth_state_main(["--email", "u@example.test", "--password", "secret", "--output", str(output)])
    assert rc == 0
    assert str(output) in capsys.readouterr().out


def test_auth_state_cli_module_entrypoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "state.json"

    monkeypatch.setattr(djvrt.auth_state, "create_form_auth_state", lambda **_: output)
    sys.modules.pop("djvrt.auth_state_cli", None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "djvrt.auth_state_cli",
            "--email",
            "u@example.test",
            "--password",
            "secret",
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("djvrt.auth_state_cli", run_name="__main__")
    assert exc.value.code == 0
