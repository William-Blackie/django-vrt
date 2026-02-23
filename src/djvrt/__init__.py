"""django-vrt package."""

from importlib.metadata import PackageNotFoundError, version

from djvrt.django_seed import (
    BaseDjangoVRTSeeder,
    Mutation,
    SeedBuildResult,
    SeedOptions,
    SeedResult,
    Variant,
    build_tree_shaken_variants,
    generate_variants_for_schema,
    snake_to_lower_camel,
)

__all__ = [
    "__version__",
    "BaseDjangoVRTSeeder",
    "Mutation",
    "SeedBuildResult",
    "SeedOptions",
    "SeedResult",
    "Variant",
    "build_tree_shaken_variants",
    "generate_variants_for_schema",
    "snake_to_lower_camel",
]

try:
    __version__ = version("django-vrt")
except PackageNotFoundError:
    __version__ = "0.0.0+local"
