from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from typing import Any, cast

import pytest

from djvrt.utils import absolute_url, canonical_json, ensure_django_ready, resolve_path, sha256_text, slugify


def test_utils_helpers_cover_url_and_path_variants(tmp_path: Path) -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert len(sha256_text("abc", length=8)) == 8
    assert slugify("Hi there / world!") == "hi-there-world"
    assert slugify("!!!") == "scenario"
    assert absolute_url("http://example.test", "about") == "http://example.test/about"
    assert absolute_url("http://example.test", "https://external.test/x") == "https://external.test/x"
    assert resolve_path(tmp_path, "a/b.txt") == tmp_path / "a/b.txt"
    assert resolve_path(tmp_path, str((tmp_path / "a.txt").resolve())) == (tmp_path / "a.txt").resolve()


def test_ensure_django_ready_errors_without_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    with pytest.raises(RuntimeError, match="DJANGO_SETTINGS_MODULE"):
        ensure_django_ready()


def test_ensure_django_ready_sets_up_django_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    setup_calls: list[str] = []
    fake_apps = types.SimpleNamespace(ready=False)

    django_module = types.ModuleType("django")
    cast_module = cast(Any, django_module)
    cast_module.setup = lambda: setup_calls.append("setup")
    django_apps_module = types.ModuleType("django.apps")
    cast_apps_module = cast(Any, django_apps_module)
    cast_apps_module.apps = fake_apps

    monkeypatch.setitem(sys.modules, "django", django_module)
    monkeypatch.setitem(sys.modules, "django.apps", django_apps_module)

    ensure_django_ready("proj.settings")
    assert os.environ["DJANGO_SETTINGS_MODULE"] == "proj.settings"
    assert setup_calls == ["setup"]

    fake_apps.ready = True
    ensure_django_ready()
    assert setup_calls == ["setup"]
