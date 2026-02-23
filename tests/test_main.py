from __future__ import annotations

import runpy

import pytest

import djvrt.cli


def test_module_main_invokes_cli_app(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"value": False}

    def fake_app() -> None:
        called["value"] = True

    monkeypatch.setattr(djvrt.cli, "app", fake_app)
    runpy.run_module("djvrt.__main__", run_name="__main__")
    assert called["value"] is True
