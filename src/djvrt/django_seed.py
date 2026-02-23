from __future__ import annotations

import copy
import json
import re
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PathToken = str | int
PathValue = tuple[PathToken, ...]


@dataclass(frozen=True)
class SeedOptions:
    scenario_file: Path
    manifest_file: Path
    include_types: tuple[str, ...] | None = None
    max_variants_per_type: int = 24
    tree_shake: bool = True
    extra_context: dict[str, Any] = None

    @property
    def extra(self) -> dict[str, Any]:
        return self.extra_context or {}

    def get_extra(self, key: str, default: Any = None) -> Any:
        return self.extra.get(key, default)


@dataclass(frozen=True)
class SeedResult:
    project_id: int
    project_sid: str
    scenario_count: int
    experiment_count: int
    scenario_file: Path
    manifest_file: Path


@dataclass(frozen=True)
class SeedBuildResult:
    project_id: int
    project_sid: str
    experiment_count: int
    scenarios: list[dict[str, Any]]
    manifest: dict[str, Any]


@dataclass(frozen=True)
class Mutation:
    path: PathValue
    value: Any


@dataclass(frozen=True)
class Variant:
    name: str
    slug: str
    config: dict[str, Any]
    mutation: Mutation | None = None

    @property
    def mutation_path(self) -> str | None:
        if self.mutation is None:
            return None
        return '.'.join(str(chunk) for chunk in self.mutation.path)


def snake_to_lower_camel(value: str) -> str:
    parts = value.split('_')
    if not parts:
        return value
    return parts[0] + ''.join(item.capitalize() for item in parts[1:])


def _slugify(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')
    return slug or 'variant'


def _has_type(schema: dict[str, Any], expected: str) -> bool:
    schema_type = schema.get('type')
    if isinstance(schema_type, str):
        return schema_type == expected
    if isinstance(schema_type, list):
        return expected in schema_type
    return False


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def _default_for_schema(schema: dict[str, Any]) -> Any:
    if 'default' in schema:
        return copy.deepcopy(schema['default'])

    if _has_type(schema, 'boolean'):
        return False

    if 'enum' in schema and isinstance(schema['enum'], list) and schema['enum']:
        return schema['enum'][0]

    if _has_type(schema, 'integer') or _has_type(schema, 'number'):
        minimum = schema.get('minimum')
        if isinstance(minimum, int | float):
            return minimum
        return 0

    if _has_type(schema, 'array'):
        return []

    if _has_type(schema, 'object') or 'properties' in schema:
        return {}

    return None


def _candidate_values(schema: dict[str, Any], current_value: Any) -> list[Any]:
    if _has_type(schema, 'boolean'):
        if not isinstance(current_value, bool):
            current_value = False
        return [not current_value]

    enum_values = schema.get('enum')
    if isinstance(enum_values, list) and enum_values:
        if current_value not in enum_values:
            current_value = enum_values[0]
        return [enum_value for enum_value in enum_values if enum_value != current_value]

    if (_has_type(schema, 'integer') or _has_type(schema, 'number')) and isinstance(
        current_value, int | float
    ):
        candidates: list[Any] = []
        minimum = schema.get('minimum')
        maximum = schema.get('maximum')

        if isinstance(minimum, int | float) and minimum != current_value:
            candidates.append(minimum)

        if isinstance(maximum, int | float) and maximum != current_value:
            candidates.append(maximum)

        if not candidates:
            step = 1 if _has_type(schema, 'integer') else 0.5
            next_value = current_value + step
            if maximum is None or next_value <= maximum:
                candidates.append(next_value)

        return candidates[:2]

    return []


def _collect_mutations(
    schema: dict[str, Any],
    current_value: Any,
    path: PathValue = (),
) -> list[Mutation]:
    mutations: list[Mutation] = []

    candidates = _candidate_values(schema, current_value)
    if candidates and path:
        for candidate in candidates:
            mutations.append(Mutation(path=path, value=candidate))
        return mutations

    if _has_type(schema, 'array'):
        items_schema = schema.get('items')
        if (
            isinstance(items_schema, dict)
            and isinstance(current_value, list)
            and current_value
            and isinstance(items_schema.get('enum'), list)
        ):
            current_item = current_value[0]
            for candidate in _candidate_values(items_schema, current_item):
                mutations.append(Mutation(path=path + (0,), value=candidate))
        return mutations

    properties = schema.get('properties')
    if _has_type(schema, 'object') or isinstance(properties, dict):
        current_object = current_value if isinstance(current_value, dict) else {}
        for key in sorted((properties or {}).keys()):
            sub_schema = properties[key]
            sub_value = current_object.get(key, _default_for_schema(sub_schema))
            mutations.extend(_collect_mutations(sub_schema, sub_value, path + (key,)))

    return mutations


def _set_nested_value(payload: dict[str, Any], path: PathValue, value: Any) -> None:
    if not path:
        msg = 'Cannot mutate root payload without a path.'
        raise ValueError(msg)

    cursor: Any = payload
    for index, token in enumerate(path[:-1]):
        next_token = path[index + 1]

        if isinstance(token, int):
            if not isinstance(cursor, list):
                msg = f'Expected list at path segment {token!r}'
                raise ValueError(msg)
            while len(cursor) <= token:
                cursor.append([] if isinstance(next_token, int) else {})
            cursor = cursor[token]
            continue

        if not isinstance(cursor, dict):
            msg = f'Expected object at path segment {token!r}'
            raise ValueError(msg)

        if token not in cursor or not isinstance(cursor[token], dict | list):
            cursor[token] = [] if isinstance(next_token, int) else {}

        cursor = cursor[token]

    last_token = path[-1]
    if isinstance(last_token, int):
        if not isinstance(cursor, list):
            msg = f'Expected list at path segment {last_token!r}'
            raise ValueError(msg)
        while len(cursor) <= last_token:
            cursor.append(None)
        cursor[last_token] = value
        return

    if not isinstance(cursor, dict):
        msg = f'Expected object at path segment {last_token!r}'
        raise ValueError(msg)

    cursor[last_token] = value


def _mutation_slug(mutation: Mutation) -> str:
    path_label = '-'.join(str(chunk) for chunk in mutation.path)
    value_label = str(mutation.value).lower()
    return _slugify(f'{path_label}-{value_label}')


def generate_variants_for_schema(
    *,
    section_schema: dict[str, Any],
    default_section: dict[str, Any],
    max_variants: int,
) -> list[Variant]:
    max_variants = max(1, max_variants)

    variants: list[Variant] = [
        Variant(name='control', slug='control', config=copy.deepcopy(default_section))
    ]
    if max_variants == 1:
        return variants

    raw_mutations = _collect_mutations(section_schema, default_section)

    deduped_mutations: list[Mutation] = []
    seen_mutations: set[tuple[PathValue, str]] = set()
    for mutation in raw_mutations:
        signature = (mutation.path, _stable_json(mutation.value))
        if signature in seen_mutations:
            continue
        seen_mutations.add(signature)
        deduped_mutations.append(mutation)

    deduped_mutations.sort(key=lambda item: (item.path, _stable_json(item.value)))

    seen_configs = {_stable_json(variants[0].config)}
    seen_slugs = {'control'}

    for mutation in deduped_mutations:
        if len(variants) >= max_variants:
            break

        mutated = copy.deepcopy(default_section)
        try:
            _set_nested_value(mutated, mutation.path, mutation.value)
        except ValueError:
            continue

        config_fingerprint = _stable_json(mutated)
        if config_fingerprint in seen_configs:
            continue

        base_slug = _mutation_slug(mutation)
        slug = base_slug
        suffix = 2
        while slug in seen_slugs:
            slug = f'{base_slug}-{suffix}'
            suffix += 1

        seen_configs.add(config_fingerprint)
        seen_slugs.add(slug)
        variants.append(
            Variant(
                name=slug.replace('-', '_'),
                slug=slug,
                config=mutated,
                mutation=mutation,
            )
        )

    return variants


def build_tree_shaken_variants(
    *,
    experiment_types: list[str],
    config_schema: dict[str, Any],
    default_config: dict[str, Any],
    max_variants_per_type: int,
    tree_shake: bool,
    config_key_resolver: Callable[[str], str] = snake_to_lower_camel,
) -> dict[str, list[Variant]]:
    schema_properties = config_schema.get('properties', {})

    variants_by_type: dict[str, list[Variant]] = {}
    for experiment_type in sorted(set(experiment_types)):
        config_key = config_key_resolver(experiment_type)
        section_schema = schema_properties.get(config_key, {})
        section_default = copy.deepcopy(default_config.get(config_key, {}))

        if tree_shake:
            variants = generate_variants_for_schema(
                section_schema=section_schema,
                default_section=section_default,
                max_variants=max_variants_per_type,
            )
        else:
            variants = [Variant(name='control', slug='control', config=section_default)]

        variants_by_type[experiment_type] = variants

    return variants_by_type


class BaseDjangoVRTSeeder(ABC):
    auth_profile_name = 'seeded_user'
    default_viewports = ('desktop', 'mobile')

    @property
    @abstractmethod
    def all_experiment_types(self) -> list[str]:
        """Return the supported experiment type identifiers."""

    @property
    @abstractmethod
    def config_schema(self) -> dict[str, Any]:
        """Return the global experiment config schema."""

    @abstractmethod
    def get_default_config(self) -> dict[str, Any]:
        """Return the default global experiment config payload."""

    def config_key_for_experiment_type(self, experiment_type: str) -> str:
        return snake_to_lower_camel(experiment_type)

    @abstractmethod
    def build_seed(
        self,
        *,
        options: SeedOptions,
        experiment_types: list[str],
        default_config: dict[str, Any],
        variants_by_type: dict[str, list[Variant]],
    ) -> SeedBuildResult:
        """Create/update data and return scenarios + manifest payloads."""

    def resolve_experiment_types(self, include_types: tuple[str, ...] | None) -> list[str]:
        allowed = set(self.all_experiment_types)
        if not include_types:
            return sorted(allowed)

        invalid = sorted(set(include_types) - allowed)
        if invalid:
            invalid_list = ', '.join(invalid)
            msg = f'Unknown experiment types: {invalid_list}'
            raise ValueError(msg)

        return sorted(set(include_types))

    def build_scenario_entry(
        self,
        *,
        scenario_id: str,
        url: str,
        tags: list[str],
        wait_for_selector: str = 'form',
        wait_for_timeout_ms: int = 700,
        full_page: bool = True,
    ) -> dict[str, Any]:
        return {
            'id': scenario_id,
            'url': url,
            'tags': tags,
            'auth_profiles': [self.auth_profile_name],
            'viewports': list(self.default_viewports),
            'wait_for_selector': wait_for_selector,
            'wait_for_timeout_ms': wait_for_timeout_ms,
            'full_page': full_page,
        }

    @staticmethod
    def variant_manifest_entry(variant: Variant) -> dict[str, Any]:
        return {
            'name': variant.name,
            'slug': variant.slug,
            'mutation_path': variant.mutation_path,
            'mutation_value': variant.mutation.value if variant.mutation else None,
        }

    @staticmethod
    def get_stable_id(*, base: int, block_size: int, slot: int, index: int) -> int:
        return base + (slot * block_size) + index + 1

    @staticmethod
    def ensure_user(
        email: str,
        password: str,
        *,
        name: str = "VRT Seed User",
        is_staff: bool = False,
        is_superuser: bool = False,
    ) -> Any:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        username_field = getattr(User, "USERNAME_FIELD", "username")

        defaults = {"is_staff": is_staff, "is_superuser": is_superuser}
        if hasattr(User, "name"):
            defaults["name"] = name
        elif hasattr(User, "first_name"):
            defaults["first_name"] = name

        user, created = User.objects.get_or_create(**{username_field: email}, defaults=defaults)

        changed = []
        if created or not user.check_password(password):
            user.set_password(password)
            changed.append("password")

        for attr, val in [("is_staff", is_staff), ("is_superuser", is_superuser)]:
            if getattr(user, attr) != val:
                setattr(user, attr, val)
                changed.append(attr)

        # Common 'is_verified' flag in many custom user models
        if hasattr(user, "is_verified") and not user.is_verified:
            user.is_verified = True
            changed.append("is_verified")

        if changed:
            user.save(update_fields=changed)
        return user

    @staticmethod
    def ensure_waffle_flag(name: str, everyone: bool = True) -> Any:
        """Idempotently ensure a django-waffle flag exists and is set for everyone."""
        try:
            from waffle.models import Flag
        except ImportError:
            return None

        flag, _ = Flag.objects.get_or_create(name=name)
        if flag.everyone != everyone:
            flag.everyone = everyone
            flag.save(update_fields=["everyone"])
        return flag

    @staticmethod
    def read_asset_bytes(assets_root: Path, relative_path: str) -> bytes:
        """Read bytes from a file relative to an assets root, with safety checks."""
        path = (assets_root / relative_path).resolve()
        if not path.exists():
            msg = f"Seed asset not found: {path}"
            raise FileNotFoundError(msg)
        return path.read_bytes()

    def run(self, options: SeedOptions) -> SeedResult:
        if options.max_variants_per_type < 1:
            msg = 'max_variants_per_type must be at least 1'
            raise ValueError(msg)

        options.scenario_file.parent.mkdir(parents=True, exist_ok=True)
        options.manifest_file.parent.mkdir(parents=True, exist_ok=True)

        experiment_types = self.resolve_experiment_types(options.include_types)
        default_config = self.get_default_config()

        variants_by_type = build_tree_shaken_variants(
            experiment_types=experiment_types,
            config_schema=self.config_schema,
            default_config=default_config,
            max_variants_per_type=options.max_variants_per_type,
            tree_shake=options.tree_shake,
            config_key_resolver=self.config_key_for_experiment_type,
        )

        build_result = self.build_seed(
            options=options,
            experiment_types=experiment_types,
            default_config=default_config,
            variants_by_type=variants_by_type,
        )

        scenario_ids = [scenario['id'] for scenario in build_result.scenarios]
        scenario_id_counts = Counter(scenario_ids)
        duplicates = sorted(
            scenario_id for scenario_id, count in scenario_id_counts.items() if count > 1
        )
        if duplicates:
            duplicate_preview = ', '.join(duplicates[:5])
            msg = f'Duplicate scenario ids generated by seeder: {duplicate_preview}'
            raise ValueError(msg)

        scenarios = sorted(build_result.scenarios, key=lambda item: item['id'])
        options.scenario_file.write_text(
            json.dumps(scenarios, indent=2, sort_keys=True),
            encoding='utf-8',
        )
        options.manifest_file.write_text(
            json.dumps(build_result.manifest, indent=2, sort_keys=True),
            encoding='utf-8',
        )

        return SeedResult(
            project_id=build_result.project_id,
            project_sid=build_result.project_sid,
            scenario_count=len(scenarios),
            experiment_count=build_result.experiment_count,
            scenario_file=options.scenario_file,
            manifest_file=options.manifest_file,
        )
