from __future__ import annotations

import argparse
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

from djvrt.django_seed import BaseDjangoVRTSeeder, SeedOptions


def _load_object(path: str) -> Any:
    if ":" not in path:
        msg = f"Invalid dotted path '{path}'. Expected 'module:object'."
        raise ValueError(msg)

    module_name, object_name = path.split(":", 1)
    if not module_name or not object_name:
        msg = f"Invalid dotted path '{path}'. Expected 'module:object'."
        raise ValueError(msg)

    module = __import__(module_name, fromlist=[object_name])
    if not hasattr(module, object_name):
        msg = f"Object '{object_name}' not found in module '{module_name}'."
        raise ValueError(msg)
    return getattr(module, object_name)


def _parse_extra_options(pairs: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            msg = f"Invalid --option value '{pair}'. Expected key=value."
            raise ValueError(msg)
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            msg = f"Invalid --option value '{pair}'. Key cannot be empty."
            raise ValueError(msg)
        parsed[key] = value
    return parsed


def _call_setup(setup_callable: Callable[..., Any], settings_module: str | None) -> None:
    signature = inspect.signature(setup_callable)
    if len(signature.parameters) == 0:
        setup_callable()
        return
    setup_callable(settings_module)


def _build_seed_options(
    *,
    options_builder: Callable[..., Any] | None,
    scenario_file: Path,
    manifest_file: Path,
    include_types: tuple[str, ...] | None,
    max_variants_per_type: int,
    tree_shake: bool,
    extra_options: dict[str, str],
) -> Any:
    base_kwargs: dict[str, Any] = {
        "scenario_file": scenario_file,
        "manifest_file": manifest_file,
        "include_types": include_types,
        "max_variants_per_type": max_variants_per_type,
        "tree_shake": tree_shake,
        "extra_context": extra_options,
    }

    if options_builder is None:
        return SeedOptions(**base_kwargs)

    signature = inspect.signature(options_builder)
    accepts_extra = "extra_options" in signature.parameters
    kwargs = {
        "scenario_file": scenario_file,
        "manifest_file": manifest_file,
        "include_types": include_types,
        "max_variants_per_type": max_variants_per_type,
        "tree_shake": tree_shake,
    }
    if accepts_extra:
        kwargs["extra_options"] = extra_options
    elif extra_options:
        kwargs.update(extra_options)

    return options_builder(**kwargs)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic Django VRT seeding via configurable project hooks."
    )
    parser.add_argument(
        "--seeder",
        required=True,
        help="Seeder class path in module:Class format (subclass of BaseDjangoVRTSeeder).",
    )
    parser.add_argument(
        "--setup",
        default=None,
        help="Optional setup callable path module:function, called before seeding.",
    )
    parser.add_argument(
        "--options-builder",
        default=None,
        help="Optional options builder callable path module:function.",
    )
    parser.add_argument(
        "--settings",
        default=None,
        help="Optional DJANGO_SETTINGS_MODULE override passed to setup callable.",
    )
    parser.add_argument(
        "--scenario-file",
        default=".djvrt/scenarios.json",
        help="Path to write generated djvrt scenarios JSON.",
    )
    parser.add_argument(
        "--manifest-file",
        default=".djvrt/tree_shake_manifest.json",
        help="Path to write tree-shake manifest JSON.",
    )
    parser.add_argument(
        "--include-type",
        action="append",
        default=None,
        help="Experiment type to include. Can be passed multiple times.",
    )
    parser.add_argument(
        "--max-variants-per-type",
        type=int,
        default=24,
        help="Maximum number of variants per experiment type (includes control).",
    )
    parser.add_argument(
        "--no-tree-shake",
        action="store_true",
        help="Disable tree-shaking and only generate control variants.",
    )
    parser.add_argument(
        "--option",
        action="append",
        default=[],
        help="Optional key=value pair passed to options builder.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_variants_per_type < 1:
        msg = "--max-variants-per-type must be at least 1"
        raise ValueError(msg)

    seeder_class = _load_object(args.seeder)
    if not inspect.isclass(seeder_class) or not issubclass(seeder_class, BaseDjangoVRTSeeder):
        msg = f"--seeder must point to a BaseDjangoVRTSeeder subclass, got {seeder_class!r}"
        raise ValueError(msg)

    setup_callable: Callable[..., Any] | None = None
    if args.setup:
        setup_obj = _load_object(args.setup)
        if not callable(setup_obj):
            msg = f"--setup must point to a callable, got {setup_obj!r}"
            raise ValueError(msg)
        setup_callable = setup_obj

    options_builder: Callable[..., Any] | None = None
    if args.options_builder:
        options_builder_obj = _load_object(args.options_builder)
        if not callable(options_builder_obj):
            msg = f"--options-builder must point to a callable, got {options_builder_obj!r}"
            raise ValueError(msg)
        options_builder = options_builder_obj

    if setup_callable is not None:
        _call_setup(setup_callable, args.settings)

    extra_options = _parse_extra_options(args.option)
    if extra_options and options_builder is None:
        msg = "Extra --option values require --options-builder"
        raise ValueError(msg)

    seed_options = _build_seed_options(
        options_builder=options_builder,
        scenario_file=Path(args.scenario_file).resolve(),
        manifest_file=Path(args.manifest_file).resolve(),
        include_types=tuple(args.include_type) if args.include_type else None,
        max_variants_per_type=args.max_variants_per_type,
        tree_shake=not args.no_tree_shake,
        extra_options=extra_options,
    )

    result = seeder_class().run(seed_options)

    print(
        "Seeded VRT data for project "
        f"{result.project_sid} ({result.experiment_count} experiments, {result.scenario_count} scenarios)."
    )
    print(f"Scenarios: {result.scenario_file}")
    print(f"Manifest: {result.manifest_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
