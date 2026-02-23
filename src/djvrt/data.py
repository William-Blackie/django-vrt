from __future__ import annotations

import asyncio
import importlib
import inspect
import os
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from djvrt.models import DJVRTConfig
from djvrt.utils import resolve_path

DataPhase = Literal["discover", "baseline", "check"]


class DataPreparationError(RuntimeError):
    """Raised when data preparation fails."""


@dataclass(frozen=True)
class DataContext:
    project_root: Path
    config_path: Path
    phase: DataPhase
    run_id: str | None = None
    lock_hash: str | None = None


@dataclass
class DataPreparationResult:
    executed_commands: list[str] = field(default_factory=list)
    loader_called: bool = False


def _parse_loader_spec(loader_spec: str) -> tuple[str, str]:
    if ":" not in loader_spec:
        msg = f"Invalid data.loader value '{loader_spec}'. Expected 'module:function'."
        raise DataPreparationError(msg)

    module_name, function_name = loader_spec.split(":", 1)
    if not module_name or not function_name:
        msg = f"Invalid data.loader value '{loader_spec}'. Expected 'module:function'."
        raise DataPreparationError(msg)

    return module_name, function_name


def _load_loader(loader_spec: str) -> Callable[[DataContext], Any]:
    module_name, function_name = _parse_loader_spec(loader_spec)

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        msg = f"Failed importing data loader module '{module_name}': {exc}"
        raise DataPreparationError(msg) from exc

    loader = getattr(module, function_name, None)
    if loader is None or not callable(loader):
        msg = f"Data loader '{loader_spec}' is not callable"
        raise DataPreparationError(msg)

    return cast(Callable[[DataContext], Any], loader)


def _run_command(command: str, *, cwd: Path, env: dict[str, str]) -> None:
    completed = subprocess.run(
        command,
        shell=True,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message_parts = [
            f"Data preparation command failed (exit={completed.returncode}): {command}",
        ]
        if completed.stdout.strip():
            message_parts.append(f"stdout:\n{completed.stdout.strip()}")
        if completed.stderr.strip():
            message_parts.append(f"stderr:\n{completed.stderr.strip()}")
        raise DataPreparationError("\n".join(message_parts))


async def _await_result(awaitable: Awaitable[Any]) -> None:
    await awaitable


def _run_loader(loader: Callable[[DataContext], Any], context: DataContext) -> None:
    result = loader(context)
    if inspect.isawaitable(result):
        asyncio.run(_await_result(result))


def prepare_data(config: DJVRTConfig, *, context: DataContext) -> DataPreparationResult:
    result = DataPreparationResult()
    data_config = config.data

    if not data_config.enabled:
        return result

    if context.phase not in data_config.phases:
        return result

    cwd = resolve_path(context.project_root, data_config.cwd) if data_config.cwd else context.project_root

    env = os.environ.copy()
    env.update(data_config.env)
    env["DJVRT_PHASE"] = context.phase
    if context.run_id:
        env["DJVRT_RUN_ID"] = context.run_id
    if context.lock_hash:
        env["DJVRT_LOCK_HASH"] = context.lock_hash

    for command in data_config.commands:
        try:
            _run_command(command, cwd=cwd, env=env)
            result.executed_commands.append(command)
        except DataPreparationError:
            if data_config.fail_on_error:
                raise

    if data_config.loader:
        loader = _load_loader(data_config.loader)
        try:
            _run_loader(loader, context)
            result.loader_called = True
        except Exception as exc:
            if data_config.fail_on_error:
                if isinstance(exc, DataPreparationError):
                    raise
                msg = f"Data loader '{data_config.loader}' failed: {exc}"
                raise DataPreparationError(msg) from exc

    return result
