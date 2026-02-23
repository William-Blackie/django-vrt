from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, Locator

from djvrt.models import CaptureOutcome, DJVRTConfig, LockedScenario, Lockfile
from djvrt.utils import resolve_path


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()


def image_filename(scenario: LockedScenario) -> str:
    return (
        f"{_safe_name(scenario.id)}--{_safe_name(scenario.viewport_name)}"
        f"--{_safe_name(scenario.auth_profile)}--{_safe_name(scenario.experiment_name)}--{scenario.key}.png"
    )


def scenario_js_random_seed(*, base_seed: int, scenario_key: str) -> int:
    payload = f"{base_seed}:{scenario_key}".encode()
    digest = hashlib.blake2s(payload, digest_size=4).digest()
    return int.from_bytes(digest, "big")


def js_random_init_script(seed: int) -> str:
    # Playwright executes this before any page script, making Math.random deterministic.
    return (
        "(() => {"
        f"let state = {seed & 0xFFFFFFFF} >>> 0;"
        "Math.random = () => {"
        "state = (Math.imul(1664525, state) + 1013904223) >>> 0;"
        "return state / 4294967296;"
        "};"
        "})();"
    )


async def _capture_one(
    browser: Browser,
    scenario: LockedScenario,
    *,
    config: DJVRTConfig,
    project_root: Path,
    output_dir: Path,
) -> CaptureOutcome:
    image_path = output_dir / image_filename(scenario)

    context_kwargs: dict[str, Any] = {
        "viewport": {"width": scenario.width, "height": scenario.height},
        "locale": config.runtime.locale,
        "timezone_id": config.runtime.timezone,
    }

    if scenario.headers:
        context_kwargs["extra_http_headers"] = scenario.headers

    if scenario.storage_state:
        storage_state_path = resolve_path(project_root, scenario.storage_state)
        if not storage_state_path.exists():
            return CaptureOutcome(
                key=scenario.key,
                status="error",
                error=f"storage_state not found: {storage_state_path}",
            )
        context_kwargs["storage_state"] = str(storage_state_path)

    context = None
    try:
        context = await browser.new_context(**context_kwargs)
        if config.runtime.js_random_seed is not None:
            seed = scenario_js_random_seed(
                base_seed=config.runtime.js_random_seed,
                scenario_key=scenario.key,
            )
            await context.add_init_script(script=js_random_init_script(seed))
        page = await context.new_page()

        await page.goto(
            scenario.url,
            wait_until=config.runtime.wait_until,
            timeout=config.runtime.navigation_timeout_ms,
        )

        if scenario.wait_for_selector:
            await page.wait_for_selector(
                scenario.wait_for_selector,
                timeout=config.runtime.navigation_timeout_ms,
            )

        if scenario.wait_for_timeout_ms > 0:
            await page.wait_for_timeout(scenario.wait_for_timeout_ms)

        if scenario.hide_selectors:
            selector_group = ", ".join(scenario.hide_selectors)
            css = f"{selector_group} {{ visibility: hidden !important; }}"
            await page.add_style_tag(content=css)

        masks: list[Locator] = []
        for selector in scenario.mask_selectors:
            locator = page.locator(selector)
            count = await locator.count()
            for index in range(min(count, 50)):
                masks.append(locator.nth(index))

        await page.screenshot(
            path=str(image_path),
            full_page=scenario.full_page,
            animations="disabled",
            mask=masks if masks else None,
        )

        return CaptureOutcome(
            key=scenario.key,
            status="ok",
            image_path=str(image_path),
        )
    except Exception as exc:
        return CaptureOutcome(
            key=scenario.key,
            status="error",
            error=str(exc),
        )
    finally:
        if context is not None:
            await context.close()


async def _capture_async(
    lockfile: Lockfile,
    *,
    config: DJVRTConfig,
    project_root: Path,
    output_dir: Path,
    scenario_keys: set[str] | None,
    progress_callback: Callable[[int, int], None] | None,
) -> dict[str, CaptureOutcome]:
    from playwright.async_api import async_playwright

    output_dir.mkdir(parents=True, exist_ok=True)

    selected = [scenario for scenario in lockfile.scenarios if scenario_keys is None or scenario.key in scenario_keys]

    if not selected:
        return {}

    semaphore = asyncio.Semaphore(config.runtime.workers)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=config.runtime.headless,
            channel=config.runtime.browser_channel,
            args=config.runtime.launch_args,
        )

        async def worker(scenario: LockedScenario) -> CaptureOutcome:
            async with semaphore:
                return await _capture_one(
                    browser,
                    scenario,
                    config=config,
                    project_root=project_root,
                    output_dir=output_dir,
                )

        results: list[CaptureOutcome] = []
        tasks = [asyncio.create_task(worker(scenario)) for scenario in selected]
        total = len(tasks)
        completed = 0
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            completed += 1
            if progress_callback is not None:
                progress_callback(completed, total)
        await browser.close()

    return {result.key: result for result in results}


def capture_scenarios(
    lockfile: Lockfile,
    *,
    config: DJVRTConfig,
    project_root: Path,
    output_dir: Path,
    scenario_keys: set[str] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, CaptureOutcome]:
    return asyncio.run(
        _capture_async(
            lockfile,
            config=config,
            project_root=project_root,
            output_dir=output_dir,
            scenario_keys=scenario_keys,
            progress_callback=progress_callback,
        )
    )
