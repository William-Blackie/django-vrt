import importlib
from importlib import metadata

import pytest

from djvrt import __version__ as package_version


def test_package_version_matches_distribution_metadata() -> None:
    assert package_version == metadata.version("django-vrt")


def test_package_version_falls_back_when_distribution_metadata_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_not_found(_: str) -> str:
        raise metadata.PackageNotFoundError

    monkeypatch.setattr(metadata, "version", _raise_not_found)
    module = importlib.reload(importlib.import_module("djvrt"))
    assert module.__version__ == "0.0.0+local"
