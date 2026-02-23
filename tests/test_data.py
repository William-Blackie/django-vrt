from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

from djvrt.data import DataContext, DataPreparationError, prepare_data
from djvrt.models import DataConfig, DJVRTConfig


def test_prepare_data_returns_empty_when_disabled(tmp_path: Path) -> None:
    config = DJVRTConfig(data=DataConfig(enabled=False, commands=["echo hello"]))
    result = prepare_data(
        config,
        context=DataContext(
            project_root=tmp_path,
            config_path=tmp_path / "djvrt.toml",
            phase="baseline",
        ),
    )
    assert result.executed_commands == []
    assert result.loader_called is False


def test_prepare_data_runs_commands_with_context_env(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()

    script_path = tmp_path / "write_marker.py"
    output_path = tmp_path / "marker.txt"
    script_path.write_text(
        "import os\n"
        "import pathlib\n"
        "import sys\n"
        "pathlib.Path(sys.argv[1]).write_text("
        "f\"{os.environ.get('DJVRT_PHASE', '')}|{os.getcwd()}\", encoding='utf-8')\n",
        encoding="utf-8",
    )

    command = " ".join(
        [
            shlex.quote(sys.executable),
            shlex.quote(str(script_path)),
            shlex.quote(str(output_path)),
        ]
    )

    config = DJVRTConfig(
        data=DataConfig(enabled=True, commands=[command], phases=["baseline"]),
    )

    result = prepare_data(
        config,
        context=DataContext(
            project_root=project_root,
            config_path=tmp_path / "djvrt.toml",
            phase="baseline",
            run_id="run-1",
            lock_hash="abc123",
        ),
    )

    assert result.executed_commands == [command]
    marker_content = output_path.read_text(encoding="utf-8")
    assert marker_content == f"baseline|{project_root}"


def test_prepare_data_respects_phase_filter(tmp_path: Path) -> None:
    marker = tmp_path / "should_not_exist.txt"
    command = f"{shlex.quote(sys.executable)} -c \"import pathlib; pathlib.Path('{marker}').write_text('x')\""

    config = DJVRTConfig(
        data=DataConfig(enabled=True, commands=[command], phases=["check"]),
    )

    result = prepare_data(
        config,
        context=DataContext(
            project_root=tmp_path,
            config_path=tmp_path / "djvrt.toml",
            phase="baseline",
        ),
    )

    assert result.executed_commands == []
    assert marker.exists() is False


def test_prepare_data_calls_python_loader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module_path = tmp_path / "seed_loader.py"
    marker_path = tmp_path / "loader_marker.txt"

    module_path.write_text(
        "from pathlib import Path\n"
        "def load(context):\n"
        "    Path(context.project_root / 'loader_marker.txt').write_text(context.phase, encoding='utf-8')\n",
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))

    config = DJVRTConfig(
        data=DataConfig(enabled=True, loader="seed_loader:load", phases=["discover"]),
    )

    result = prepare_data(
        config,
        context=DataContext(
            project_root=tmp_path,
            config_path=tmp_path / "djvrt.toml",
            phase="discover",
        ),
    )

    assert result.loader_called is True
    assert marker_path.read_text(encoding="utf-8") == "discover"


def test_prepare_data_can_seed_django_models_repeatably(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite3"
    settings_module = "djvrt_test_settings"

    (tmp_path / f"{settings_module}.py").write_text(
        "SECRET_KEY = 'test-key'\n"
        "DEBUG = False\n"
        "USE_TZ = True\n"
        "TIME_ZONE = 'UTC'\n"
        "INSTALLED_APPS = [\n"
        "    'django.contrib.auth',\n"
        "    'django.contrib.contenttypes',\n"
        "]\n"
        "DATABASES = {\n"
        "    'default': {\n"
        "        'ENGINE': 'django.db.backends.sqlite3',\n"
        f"        'NAME': r'{db_path}',\n"
        "    }\n"
        "}\n"
        "DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'\n",
        encoding="utf-8",
    )

    (tmp_path / "django_seed_loader.py").write_text(
        "import os\n"
        "from django.apps import apps\n"
        "from django.core.management import call_command\n"
        "\n"
        "def load(context):\n"
        f"    os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{settings_module}')\n"
        "    import django\n"
        "    if not apps.ready:\n"
        "        django.setup()\n"
        "    call_command('migrate', interactive=False, verbosity=0)\n"
        "    from django.contrib.auth import get_user_model\n"
        "    user_model = get_user_model()\n"
        "    user_model.objects.get_or_create(\n"
        "        username='djvrt-seeded-user',\n"
        "        defaults={'email': 'seeded@example.com'}\n"
        "    )\n",
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))

    config = DJVRTConfig(
        data=DataConfig(enabled=True, loader="django_seed_loader:load", phases=["baseline"]),
    )

    context = DataContext(
        project_root=tmp_path,
        config_path=tmp_path / "djvrt.toml",
        phase="baseline",
    )

    prepare_data(config, context=context)
    prepare_data(config, context=context)

    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    assert user_model.objects.filter(username="djvrt-seeded-user").count() == 1


def test_prepare_data_rejects_invalid_loader_spec(tmp_path: Path) -> None:
    config = DJVRTConfig(data=DataConfig(enabled=True, loader="invalid-loader", phases=["baseline"]))
    with pytest.raises(DataPreparationError, match="Expected 'module:function'"):
        prepare_data(
            config,
            context=DataContext(
                project_root=tmp_path,
                config_path=tmp_path / "djvrt.toml",
                phase="baseline",
            ),
        )


@pytest.mark.parametrize("loader", [":load", "module:"])
def test_prepare_data_rejects_loader_spec_with_empty_segments(loader: str, tmp_path: Path) -> None:
    config = DJVRTConfig(data=DataConfig(enabled=True, loader=loader, phases=["baseline"]))
    with pytest.raises(DataPreparationError, match="Expected 'module:function'"):
        prepare_data(
            config,
            context=DataContext(
                project_root=tmp_path,
                config_path=tmp_path / "djvrt.toml",
                phase="baseline",
            ),
        )


def test_prepare_data_rejects_missing_loader_module(tmp_path: Path) -> None:
    config = DJVRTConfig(data=DataConfig(enabled=True, loader="missing_module:load", phases=["baseline"]))
    with pytest.raises(DataPreparationError, match="Failed importing data loader module"):
        prepare_data(
            config,
            context=DataContext(
                project_root=tmp_path,
                config_path=tmp_path / "djvrt.toml",
                phase="baseline",
            ),
        )


def test_prepare_data_rejects_non_callable_loader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "bad_loader.py").write_text("loader = 42\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    config = DJVRTConfig(data=DataConfig(enabled=True, loader="bad_loader:loader", phases=["baseline"]))
    with pytest.raises(DataPreparationError, match="is not callable"):
        prepare_data(
            config,
            context=DataContext(
                project_root=tmp_path,
                config_path=tmp_path / "djvrt.toml",
                phase="baseline",
            ),
        )


def test_prepare_data_command_failure_includes_stdout_and_stderr(tmp_path: Path) -> None:
    command = (
        f"{shlex.quote(sys.executable)} -c "
        "\"import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(3)\""
    )
    config = DJVRTConfig(data=DataConfig(enabled=True, commands=[command], phases=["baseline"]))

    with pytest.raises(DataPreparationError, match="exit=3"):
        prepare_data(
            config,
            context=DataContext(
                project_root=tmp_path,
                config_path=tmp_path / "djvrt.toml",
                phase="baseline",
            ),
        )


def test_prepare_data_command_failure_can_be_ignored(tmp_path: Path) -> None:
    command = f'{shlex.quote(sys.executable)} -c "raise SystemExit(2)"'
    config = DJVRTConfig(
        data=DataConfig(enabled=True, commands=[command], phases=["baseline"], fail_on_error=False),
    )
    result = prepare_data(
        config,
        context=DataContext(
            project_root=tmp_path,
            config_path=tmp_path / "djvrt.toml",
            phase="baseline",
        ),
    )
    assert result.executed_commands == []


def test_prepare_data_supports_async_loader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "async_loader_marker.txt"
    (tmp_path / "async_loader.py").write_text(
        "from pathlib import Path\n"
        "async def load(context):\n"
        "    Path(context.project_root / 'async_loader_marker.txt').write_text('ok', encoding='utf-8')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    config = DJVRTConfig(data=DataConfig(enabled=True, loader="async_loader:load", phases=["baseline"]))

    result = prepare_data(
        config,
        context=DataContext(
            project_root=tmp_path,
            config_path=tmp_path / "djvrt.toml",
            phase="baseline",
        ),
    )
    assert result.loader_called is True
    assert marker_path.read_text(encoding="utf-8") == "ok"


def test_prepare_data_loader_failure_can_be_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "failing_loader.py").write_text(
        "def load(context):\n" "    raise RuntimeError('loader boom')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    config = DJVRTConfig(
        data=DataConfig(enabled=True, loader="failing_loader:load", phases=["baseline"], fail_on_error=False),
    )
    result = prepare_data(
        config,
        context=DataContext(
            project_root=tmp_path,
            config_path=tmp_path / "djvrt.toml",
            phase="baseline",
        ),
    )
    assert result.loader_called is False


def test_prepare_data_loader_failure_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "failing_loader.py").write_text(
        "def load(context):\n" "    raise RuntimeError('loader boom')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    config = DJVRTConfig(
        data=DataConfig(enabled=True, loader="failing_loader:load", phases=["baseline"], fail_on_error=True),
    )
    with pytest.raises(DataPreparationError, match="Data loader 'failing_loader:load' failed: loader boom"):
        prepare_data(
            config,
            context=DataContext(
                project_root=tmp_path,
                config_path=tmp_path / "djvrt.toml",
                phase="baseline",
            ),
        )


def test_prepare_data_reraises_data_preparation_error_from_loader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "error_loader.py").write_text(
        "from djvrt.data import DataPreparationError\n"
        "def load(context):\n"
        "    raise DataPreparationError('loader failed explicitly')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    config = DJVRTConfig(
        data=DataConfig(enabled=True, loader="error_loader:load", phases=["baseline"], fail_on_error=True),
    )
    with pytest.raises(DataPreparationError, match="loader failed explicitly"):
        prepare_data(
            config,
            context=DataContext(
                project_root=tmp_path,
                config_path=tmp_path / "djvrt.toml",
                phase="baseline",
            ),
        )
