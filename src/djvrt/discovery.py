from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import httpx

from djvrt.models import DiscoveredScenario, DJVRTConfig
from djvrt.utils import absolute_url, slugify


class DiscoveryError(RuntimeError):
    """Raised when scenario discovery cannot continue."""


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _parse_locs(xml_text: str) -> tuple[str, list[str]]:
    root = ET.fromstring(xml_text)
    root_name = _local_name(root.tag)
    locs = [loc.text.strip() for loc in root.findall(".//{*}loc") if loc.text and loc.text.strip()]
    return root_name, locs


def _discover_sitemap_recursive(
    url: str,
    *,
    client: httpx.Client,
    seen: set[str],
    max_urls: int,
) -> list[str]:
    if url in seen:
        return []
    seen.add(url)

    response = client.get(url)
    response.raise_for_status()

    root_name, locs = _parse_locs(response.text)

    if root_name == "urlset":
        return locs[:max_urls]

    if root_name != "sitemapindex":
        return []

    urls: list[str] = []
    for child in locs:
        for discovered in _discover_sitemap_recursive(
            child,
            client=client,
            seen=seen,
            max_urls=max_urls,
        ):
            if len(urls) >= max_urls:
                return urls
            urls.append(discovered)
    return urls


def discover_urls_from_sitemap(base_url: str, sitemap_url: str, max_urls: int) -> list[str]:
    start_url = absolute_url(base_url, sitemap_url)
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            urls = _discover_sitemap_recursive(start_url, client=client, seen=set(), max_urls=max_urls)
    except (httpx.HTTPError, ET.ParseError) as exc:
        msg = f"Failed to discover URLs from sitemap {start_url}: {exc}"
        raise DiscoveryError(msg) from exc

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        normalized = absolute_url(base_url, url)
        if normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
        if len(deduped) >= max_urls:
            break
    return deduped


def _sanitize_route(route: str) -> str | None:
    cleaned = route.strip().replace("^", "").replace("$", "")
    cleaned = re.sub(r"//+", "/", cleaned)

    # Dynamic paths are too unstable without explicit data fixtures.
    if any(token in cleaned for token in ("<", "(", "[", "*", "+", "?")):
        return None

    if cleaned == "":
        return "/"

    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return cleaned


def _walk_urlpatterns(prefix: str, patterns: list[object]) -> list[str]:
    from django.urls import URLPattern, URLResolver

    urls: list[str] = []

    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            route = _sanitize_route(str(pattern.pattern))
            if route is None:
                continue
            next_prefix = f"{prefix}{route}" if route != "/" else prefix
            urls.extend(_walk_urlpatterns(next_prefix, list(pattern.url_patterns)))
            continue

        if isinstance(pattern, URLPattern):
            route = _sanitize_route(str(pattern.pattern))
            if route is None:
                continue
            merged = f"{prefix}{route}" if route != "/" else prefix or "/"
            normalized = _sanitize_route(merged)
            if normalized is not None:
                urls.append(normalized)

    return urls


def discover_urls_from_django(base_url: str, settings_module: str | None = None) -> list[str]:
    if settings_module:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)

    try:
        import django
        from django.conf import settings
        from django.urls import get_resolver
    except Exception as exc:
        msg = f"Django import failed: {exc}"
        raise DiscoveryError(msg) from exc

    if not settings.configured and not os.environ.get("DJANGO_SETTINGS_MODULE"):
        msg = "DJANGO_SETTINGS_MODULE is not set. Use --settings or disable urlconf discovery."
        raise DiscoveryError(msg)

    try:
        django.setup()
        resolver = get_resolver()
        routes = _walk_urlpatterns("", list(resolver.url_patterns))
    except Exception as exc:
        msg = f"Failed walking Django URL patterns: {exc}"
        raise DiscoveryError(msg) from exc

    deduped: list[str] = []
    seen: set[str] = set()
    for route in routes:
        absolute = absolute_url(base_url, route)
        if absolute not in seen:
            seen.add(absolute)
            deduped.append(absolute)
    return deduped


def _compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def filter_urls(urls: list[str], include: list[str], exclude: list[str]) -> list[str]:
    include_patterns = _compile_patterns(include)
    exclude_patterns = _compile_patterns(exclude)

    filtered: list[str] = []

    for url in urls:
        path = urlparse(url).path or "/"

        if include_patterns and not any(pattern.search(path) for pattern in include_patterns):
            continue

        if any(pattern.search(path) for pattern in exclude_patterns):
            continue

        filtered.append(url)

    return filtered


def build_discovered_scenarios(urls: list[str]) -> list[DiscoveredScenario]:
    scenarios: list[DiscoveredScenario] = []
    id_counts: dict[str, int] = {}

    for url in urls:
        path = urlparse(url).path or "/"
        raw_id = "home" if path == "/" else slugify(path)
        count = id_counts.get(raw_id, 0)
        id_counts[raw_id] = count + 1
        scenario_id = raw_id if count == 0 else f"{raw_id}-{count + 1}"

        scenarios.append(DiscoveredScenario(id=scenario_id, url=url, tags=[]))

    return scenarios


def discover_scenarios(config: DJVRTConfig, settings_module: str | None = None) -> list[DiscoveredScenario]:
    urls: list[str] = []

    if config.discovery.use_sitemap:
        urls.extend(
            discover_urls_from_sitemap(
                config.base_url,
                config.discovery.sitemap_url,
                config.discovery.max_urls,
            )
        )

    if config.discovery.use_django_urlconf:
        urls.extend(discover_urls_from_django(config.base_url, settings_module=settings_module))

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)

    filtered = filter_urls(
        deduped,
        include=config.discovery.include,
        exclude=config.discovery.exclude,
    )

    if config.discovery.max_urls:
        filtered = filtered[: config.discovery.max_urls]

    return build_discovered_scenarios(filtered)


def read_scenarios(path: Path) -> list[DiscoveredScenario]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        msg = f"Scenario file {path} must contain a JSON array"
        raise ValueError(msg)
    return [DiscoveredScenario.model_validate(item) for item in raw]


def write_scenarios(path: Path, scenarios: list[DiscoveredScenario]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [scenario.model_dump(mode="json") for scenario in scenarios]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
