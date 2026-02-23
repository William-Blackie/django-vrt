from __future__ import annotations

import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from djvrt.models import DiscoveredScenario, DJVRTConfig, LockedScenario, LockEnvironment, Lockfile
from djvrt.utils import absolute_url, canonical_json, sha256_text, utcnow


def _unique(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _playwright_version() -> str | None:
    try:
        return version("playwright")
    except PackageNotFoundError:
        return None


def _config_digest(config: DJVRTConfig) -> str:
    return sha256_text(canonical_json(config.model_dump(mode="json")), length=32)


def _merge_query_params(url: str, query_params: dict[str, str]) -> str:
    if not query_params:
        return url

    split = urlsplit(url)
    merged = dict(parse_qsl(split.query, keep_blank_values=True))
    merged.update(query_params)

    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(merged), split.fragment))


def build_lockfile(config: DJVRTConfig, scenarios: list[DiscoveredScenario]) -> Lockfile:
    viewport_map = {viewport.name: viewport for viewport in config.viewports}
    auth_map = {auth.name: auth for auth in config.auth_profiles}
    experiment_map = {experiment.name: experiment for experiment in config.experiments}

    locked: list[LockedScenario] = []

    for scenario in scenarios:
        viewport_names = scenario.viewports or list(viewport_map)
        auth_profile_names = scenario.auth_profiles or list(auth_map)
        experiment_names = scenario.experiments or list(experiment_map)

        for viewport_name in viewport_names:
            if viewport_name not in viewport_map:
                msg = f"Unknown viewport '{viewport_name}' in scenario '{scenario.id}'"
                raise ValueError(msg)

            viewport = viewport_map[viewport_name]

            for auth_profile_name in auth_profile_names:
                if auth_profile_name not in auth_map:
                    msg = f"Unknown auth profile '{auth_profile_name}' in scenario '{scenario.id}'"
                    raise ValueError(msg)

                auth_profile = auth_map[auth_profile_name]

                for experiment_name in experiment_names:
                    if experiment_name not in experiment_map:
                        msg = f"Unknown experiment '{experiment_name}' in scenario '{scenario.id}'"
                        raise ValueError(msg)

                    experiment = experiment_map[experiment_name]

                    threshold = (
                        scenario.threshold
                        if scenario.threshold is not None
                        else config.runtime.default_mismatch_threshold
                    )
                    wait_timeout_ms = (
                        scenario.wait_for_timeout_ms
                        if scenario.wait_for_timeout_ms is not None
                        else config.runtime.settle_time_ms
                    )
                    full_page = (
                        scenario.full_page if scenario.full_page is not None else config.runtime.default_full_page
                    )

                    mask_selectors = _unique(config.runtime.default_mask_selectors + scenario.mask_selectors)
                    hide_selectors = _unique(config.runtime.default_hide_selectors + scenario.hide_selectors)

                    resolved_url = absolute_url(config.base_url, scenario.url)
                    resolved_url = _merge_query_params(resolved_url, experiment.query_params)

                    key_payload = {
                        "id": scenario.id,
                        "url": resolved_url,
                        "viewport": viewport_name,
                        "auth_profile": auth_profile_name,
                        "experiment": experiment_name,
                    }
                    key = sha256_text(canonical_json(key_payload), length=16)

                    headers = auth_profile.headers | experiment.headers

                    locked.append(
                        LockedScenario(
                            key=key,
                            id=scenario.id,
                            url=resolved_url,
                            tags=scenario.tags,
                            viewport_name=viewport_name,
                            experiment_name=experiment_name,
                            width=viewport.width,
                            height=viewport.height,
                            auth_profile=auth_profile_name,
                            storage_state=auth_profile.storage_state,
                            headers=headers,
                            threshold=threshold,
                            wait_for_selector=scenario.wait_for_selector,
                            wait_for_timeout_ms=wait_timeout_ms,
                            mask_selectors=mask_selectors,
                            hide_selectors=hide_selectors,
                            full_page=full_page,
                        )
                    )

    locked.sort(key=lambda item: (item.id, item.url, item.viewport_name, item.auth_profile, item.experiment_name))

    environment = LockEnvironment(
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        playwright_version=_playwright_version(),
    )

    config_digest = _config_digest(config)
    payload = {
        "lock_version": 1,
        "config_digest": config_digest,
        "environment": environment.model_dump(mode="json"),
        "scenarios": [item.model_dump(mode="json") for item in locked],
    }
    lock_hash = sha256_text(canonical_json(payload), length=16)

    return Lockfile(
        lock_version=1,
        generated_at=utcnow(),
        config_digest=config_digest,
        environment=environment,
        scenarios=locked,
        hash=lock_hash,
    )


def write_lockfile(path: Path, lockfile: Lockfile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = lockfile.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_lockfile(path: Path) -> Lockfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Lockfile.model_validate(payload)
