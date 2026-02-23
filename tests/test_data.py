from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

from djvrt.data import DataContext, prepare_data
from djvrt.models import DataConfig, DJVRTConfig


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
