from __future__ import annotations

import builtins
import sys
import types
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

import djvrt.discovery as discovery
from djvrt.discovery import (
    DiscoveryError,
    _discover_sitemap_recursive,
    _local_name,
    _parse_locs,
    _sanitize_route,
    _walk_urlpatterns,
    discover_scenarios,
    discover_urls_from_django,
    discover_urls_from_sitemap,
    read_scenarios,
    write_scenarios,
)
from djvrt.models import DiscoveredScenario, DJVRTConfig


class _Response:
    def __init__(self, text: str, *, raise_exc: Exception | None = None) -> None:
        self.text = text
        self._raise_exc = raise_exc

    def raise_for_status(self) -> None:
        if self._raise_exc is not None:
            raise self._raise_exc


class _Client:
    def __init__(self, mapping: dict[str, _Response]) -> None:
        self.mapping = mapping

    def get(self, url: str) -> _Response:
        return self.mapping[url]


def test_local_name_and_parse_locs() -> None:
    xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.test/</loc></url>
      <url><loc>https://example.test/about/</loc></url>
    </urlset>
    """.strip()
    root_name, locs = _parse_locs(xml)
    assert root_name == "urlset"
    assert locs == ["https://example.test/", "https://example.test/about/"]
    assert _local_name("{x}urlset") == "urlset"
    assert _local_name("urlset") == "urlset"


def test_discover_sitemap_recursive_handles_index_seen_and_max() -> None:
    index_xml = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.test/s1.xml</loc></sitemap>
      <sitemap><loc>https://example.test/s2.xml</loc></sitemap>
      <sitemap><loc>https://example.test/s1.xml</loc></sitemap>
    </sitemapindex>
    """.strip()
    s1_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.test/a</loc></url>
      <url><loc>https://example.test/b</loc></url>
    </urlset>
    """.strip()
    s2_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.test/c</loc></url>
    </urlset>
    """.strip()

    client = _Client(
        {
            "https://example.test/sitemap.xml": _Response(index_xml),
            "https://example.test/s1.xml": _Response(s1_xml),
            "https://example.test/s2.xml": _Response(s2_xml),
        }
    )
    urls = _discover_sitemap_recursive(
        "https://example.test/sitemap.xml",
        client=cast(httpx.Client, client),
        seen=set(),
        max_urls=2,
    )
    assert urls == ["https://example.test/a", "https://example.test/b"]

    unknown = _discover_sitemap_recursive(
        "https://example.test/s2.xml",
        client=cast(httpx.Client, _Client({"https://example.test/s2.xml": _Response("<root />")})),
        seen=set(),
        max_urls=10,
    )
    assert unknown == []


def test_discover_sitemap_recursive_returns_empty_when_url_already_seen() -> None:
    client = _Client({"https://example.test/sitemap.xml": _Response("<urlset />")})
    urls = _discover_sitemap_recursive(
        "https://example.test/sitemap.xml",
        client=cast(httpx.Client, client),
        seen={"https://example.test/sitemap.xml"},
        max_urls=10,
    )
    assert urls == []


def test_discover_sitemap_recursive_returns_all_urls_when_under_limit() -> None:
    index_xml = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.test/s1.xml</loc></sitemap>
      <sitemap><loc>https://example.test/s2.xml</loc></sitemap>
    </sitemapindex>
    """.strip()
    s1_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.test/a</loc></url>
    </urlset>
    """.strip()
    s2_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.test/b</loc></url>
    </urlset>
    """.strip()

    client = _Client(
        {
            "https://example.test/sitemap.xml": _Response(index_xml),
            "https://example.test/s1.xml": _Response(s1_xml),
            "https://example.test/s2.xml": _Response(s2_xml),
        }
    )
    urls = _discover_sitemap_recursive(
        "https://example.test/sitemap.xml",
        client=cast(httpx.Client, client),
        seen=set(),
        max_urls=10,
    )
    assert urls == ["https://example.test/a", "https://example.test/b"]


def test_discover_urls_from_sitemap_dedupes_and_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        discovery,
        "_discover_sitemap_recursive",
        lambda *_args, **_kwargs: ["/a", "/a", "https://example.test/b", "/c"],
    )
    urls = discover_urls_from_sitemap("https://example.test", "/sitemap.xml", 2)
    assert urls == ["https://example.test/a", "https://example.test/b"]


def test_discover_urls_from_sitemap_wraps_http_and_parse_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenClient:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> _BrokenClient:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get(self, _: str) -> _Response:
            return _Response("", raise_exc=httpx.HTTPError("boom"))

    monkeypatch.setattr("djvrt.discovery.httpx.Client", _BrokenClient)
    with pytest.raises(DiscoveryError, match="Failed to discover URLs from sitemap"):
        discover_urls_from_sitemap("https://example.test", "/sitemap.xml", 10)

    class _BadXmlClient(_BrokenClient):
        def get(self, _: str) -> _Response:
            return _Response("<not xml")

    monkeypatch.setattr("djvrt.discovery.httpx.Client", _BadXmlClient)
    with pytest.raises(DiscoveryError, match="Failed to discover URLs from sitemap"):
        discover_urls_from_sitemap("https://example.test", "/sitemap.xml", 10)


def test_sanitize_route_variants() -> None:
    assert _sanitize_route("^/about/$") == "/about/"
    assert _sanitize_route("") == "/"
    assert _sanitize_route("users") == "/users"
    assert _sanitize_route("<int:id>/") is None


def test_walk_urlpatterns_recurses_over_resolvers(monkeypatch: pytest.MonkeyPatch) -> None:
    django_urls = types.ModuleType("django.urls")

    class URLPattern:
        def __init__(self, pattern: str) -> None:
            self.pattern = pattern

    class URLResolver:
        def __init__(self, pattern: str, url_patterns: list[object]) -> None:
            self.pattern = pattern
            self.url_patterns = url_patterns

    cast(Any, django_urls).URLPattern = URLPattern
    cast(Any, django_urls).URLResolver = URLResolver
    monkeypatch.setitem(sys.modules, "django.urls", django_urls)

    patterns = [
        URLPattern("^$"),
        URLResolver(
            "shop/",
            [
                URLPattern("cart/"),
                URLPattern("<slug:item>/"),
            ],
        ),
    ]

    assert _walk_urlpatterns("", patterns) == ["/", "/shop/cart/"]


def test_walk_urlpatterns_skips_dynamic_resolver_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    django_urls = types.ModuleType("django.urls")

    class URLPattern:
        def __init__(self, pattern: str) -> None:
            self.pattern = pattern

    class URLResolver:
        def __init__(self, pattern: str, url_patterns: list[object]) -> None:
            self.pattern = pattern
            self.url_patterns = url_patterns

    cast(Any, django_urls).URLPattern = URLPattern
    cast(Any, django_urls).URLResolver = URLResolver
    monkeypatch.setitem(sys.modules, "django.urls", django_urls)

    patterns = [
        URLResolver("<int:id>/", [URLPattern("x/")]),
        URLPattern("ok/"),
    ]
    assert _walk_urlpatterns("", patterns) == ["/ok/"]


def test_discover_urls_from_django_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def failing_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "django":
            raise ImportError("no django")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    with pytest.raises(DiscoveryError, match="Django import failed"):
        discover_urls_from_django("https://example.test")

    monkeypatch.setattr(builtins, "__import__", original_import)

    django_module = types.ModuleType("django")
    cast(Any, django_module).setup = lambda: None
    django_conf = types.ModuleType("django.conf")
    cast(Any, django_conf).settings = types.SimpleNamespace(configured=False)
    django_urls = types.ModuleType("django.urls")
    cast(Any, django_urls).get_resolver = lambda: types.SimpleNamespace(url_patterns=[])
    cast(Any, django_urls).URLPattern = type("URLPattern", (), {})
    cast(Any, django_urls).URLResolver = type("URLResolver", (), {})

    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    monkeypatch.setitem(sys.modules, "django", django_module)
    monkeypatch.setitem(sys.modules, "django.conf", django_conf)
    monkeypatch.setitem(sys.modules, "django.urls", django_urls)

    with pytest.raises(DiscoveryError, match="DJANGO_SETTINGS_MODULE is not set"):
        discover_urls_from_django("https://example.test")

    django_settings = cast(Any, django_conf.settings)
    django_settings.configured = True
    cast(Any, django_module).setup = lambda: (_ for _ in ()).throw(RuntimeError("bad setup"))
    with pytest.raises(DiscoveryError, match="Failed walking Django URL patterns"):
        discover_urls_from_django("https://example.test")


def test_discover_urls_from_django_success(monkeypatch: pytest.MonkeyPatch) -> None:
    django_module = types.ModuleType("django")
    cast(Any, django_module).setup = lambda: None
    django_conf = types.ModuleType("django.conf")
    cast(Any, django_conf).settings = types.SimpleNamespace(configured=True)

    django_urls = types.ModuleType("django.urls")

    class URLPattern:
        def __init__(self, pattern: str) -> None:
            self.pattern = pattern

    class URLResolver:
        def __init__(self, pattern: str, url_patterns: list[object]) -> None:
            self.pattern = pattern
            self.url_patterns = url_patterns

    resolver = types.SimpleNamespace(
        url_patterns=[
            URLPattern("^$"),
            URLResolver("a/", [URLPattern("b/")]),
            URLPattern("^$"),
        ]
    )
    cast(Any, django_urls).get_resolver = lambda: resolver
    cast(Any, django_urls).URLPattern = URLPattern
    cast(Any, django_urls).URLResolver = URLResolver

    monkeypatch.setitem(sys.modules, "django", django_module)
    monkeypatch.setitem(sys.modules, "django.conf", django_conf)
    monkeypatch.setitem(sys.modules, "django.urls", django_urls)

    urls = discover_urls_from_django("https://example.test", settings_module="proj.settings")
    assert urls == ["https://example.test/", "https://example.test/a/b/"]


def test_discover_scenarios_combines_dedupes_and_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    config = DJVRTConfig(base_url="https://example.test")
    config.discovery.max_urls = 2
    config.discovery.include = [r"^/a|^/b"]
    config.discovery.exclude = [r"/admin"]

    monkeypatch.setattr(
        discovery,
        "discover_urls_from_sitemap",
        lambda *_: ["https://example.test/a", "https://example.test/admin"],
    )
    monkeypatch.setattr(
        discovery,
        "discover_urls_from_django",
        lambda *_args, **_kwargs: ["https://example.test/a", "https://example.test/b"],
    )

    scenarios = discover_scenarios(config)
    assert [scenario.url for scenario in scenarios] == ["https://example.test/a", "https://example.test/b"]


def test_read_and_write_scenarios_roundtrip(tmp_path: Path) -> None:
    scenarios = [
        DiscoveredScenario(id="home", url="https://example.test/"),
        DiscoveredScenario(id="about", url="https://example.test/about"),
    ]
    path = tmp_path / "scenarios.json"
    write_scenarios(path, scenarios)
    loaded = read_scenarios(path)
    assert [item.id for item in loaded] == ["home", "about"]

    path.write_text('{"bad": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a JSON array"):
        read_scenarios(path)
