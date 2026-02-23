from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, cast

import pytest

import djvrt.capture as capture
from djvrt.capture import (
    _capture_async,
    _capture_one,
    _safe_name,
    capture_scenarios,
    image_filename,
    js_random_init_script,
    scenario_js_random_seed,
)
from djvrt.models import CaptureOutcome, DJVRTConfig, LockedScenario, LockEnvironment, Lockfile


def test_scenario_js_random_seed_is_stable() -> None:
    first = scenario_js_random_seed(base_seed=2026, scenario_key="xp-acr-image-control")
    second = scenario_js_random_seed(base_seed=2026, scenario_key="xp-acr-image-control")
    assert first == second


def test_scenario_js_random_seed_changes_with_scenario() -> None:
    first = scenario_js_random_seed(base_seed=2026, scenario_key="xp-acr-image-control")
    second = scenario_js_random_seed(base_seed=2026, scenario_key="xp-acr-image-variant")
    assert first != second


def test_js_random_init_script_uses_uint32_seed() -> None:
    script = js_random_init_script((1 << 40) + 5)
    assert "let state = 5 >>> 0;" in script
    assert "Math.random = () => {" in script
    assert "Math.imul(1664525, state)" in script


def _scenario(**overrides: Any) -> LockedScenario:
    payload: dict[str, Any] = {
        "key": "home-desktop-anon-control",
        "id": "home",
        "url": "http://example.test/",
        "tags": [],
        "viewport_name": "desktop",
        "experiment_name": "control",
        "width": 1200,
        "height": 800,
        "auth_profile": "anonymous",
        "storage_state": None,
        "headers": {},
        "threshold": 0.001,
        "wait_for_selector": None,
        "wait_for_timeout_ms": 0,
        "mask_selectors": [],
        "hide_selectors": [],
        "full_page": True,
    }
    payload.update(overrides)
    return LockedScenario(**payload)


def _lockfile(*scenarios: LockedScenario) -> Lockfile:
    return Lockfile(
        lock_version=1,
        generated_at=datetime.now(UTC),
        config_digest="digest",
        environment=LockEnvironment(
            python_version="3.13",
            platform="test",
            playwright_version="1.0",
        ),
        scenarios=list(scenarios),
        hash="lock-hash",
    )


class _MaskHandle:
    def __init__(self, selector: str, index: int) -> None:
        self.selector = selector
        self.index = index


class _FakeLocator:
    def __init__(self, selector: str, count: int) -> None:
        self.selector = selector
        self._count = count

    async def count(self) -> int:
        return self._count

    def nth(self, index: int) -> _MaskHandle:
        return _MaskHandle(self.selector, index)


class _FakePage:
    def __init__(
        self,
        *,
        locator_counts: dict[str, int] | None = None,
        goto_error: Exception | None = None,
    ) -> None:
        self._locator_counts = locator_counts or {}
        self._goto_error = goto_error
        self.goto_calls: list[tuple[str, str, int]] = []
        self.wait_for_selector_calls: list[tuple[str, int]] = []
        self.wait_for_timeout_calls: list[int] = []
        self.style_calls: list[str] = []
        self.screenshot_calls: list[dict[str, Any]] = []

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append((url, wait_until, timeout))
        if self._goto_error is not None:
            raise self._goto_error

    async def wait_for_selector(self, selector: str, *, timeout: int) -> None:
        self.wait_for_selector_calls.append((selector, timeout))

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_for_timeout_calls.append(timeout_ms)

    async def add_style_tag(self, *, content: str) -> None:
        self.style_calls.append(content)

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(selector, self._locator_counts.get(selector, 0))

    async def screenshot(
        self,
        *,
        path: str,
        full_page: bool,
        animations: str,
        mask: list[_MaskHandle] | None,
    ) -> None:
        self.screenshot_calls.append(
            {
                "path": path,
                "full_page": full_page,
                "animations": animations,
                "mask": mask,
            }
        )


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.closed = False
        self.init_scripts: list[str] = []

    async def add_init_script(self, *, script: str) -> None:
        self.init_scripts.append(script)

    async def new_page(self) -> _FakePage:
        return self._page

    async def close(self) -> None:
        self.closed = True


class _FakeBrowser:
    def __init__(self, contexts: list[_FakeContext]) -> None:
        self._contexts = contexts
        self.new_context_calls: list[dict[str, Any]] = []
        self.closed = False

    async def new_context(self, **kwargs: Any) -> _FakeContext:
        self.new_context_calls.append(kwargs)
        if not self._contexts:
            msg = "No fake contexts remaining"
            raise RuntimeError(msg)
        return self._contexts.pop(0)

    async def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser) -> None:
        self._browser = browser
        self.launch_calls: list[dict[str, Any]] = []

    async def launch(self, *, headless: bool, channel: str | None, args: list[str]) -> _FakeBrowser:
        self.launch_calls.append({"headless": headless, "channel": channel, "args": args})
        return self._browser


class _FakePlaywright:
    def __init__(self, browser: _FakeBrowser) -> None:
        self.chromium = _FakeChromium(browser)


class _FakeAsyncPlaywrightContext:
    def __init__(self, playwright: _FakePlaywright) -> None:
        self._playwright = playwright

    async def __aenter__(self) -> _FakePlaywright:
        return self._playwright

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb


def test_safe_name_and_image_filename_are_stable() -> None:
    assert _safe_name("Hero Banner / V1") == "hero-banner-v1"
    filename = image_filename(
        _scenario(
            id="Hero Banner",
            viewport_name="Mobile XL",
            auth_profile="Signed In",
            experiment_name="Variant A",
            key="abc123",
        )
    )
    assert filename == "hero-banner--mobile-xl--signed-in--variant-a--abc123.png"


def test_capture_one_success_applies_runtime_and_selectors(tmp_path: Path) -> None:
    scenario = _scenario(
        storage_state="auth/user.json",
        headers={"X-Test": "yes"},
        wait_for_selector="#ready",
        wait_for_timeout_ms=250,
        mask_selectors=[".sensitive"],
        hide_selectors=[".ads", ".clock"],
    )
    config = DJVRTConfig(base_url="http://example.test")
    config.runtime.js_random_seed = 42
    config.runtime.navigation_timeout_ms = 12_345
    config.runtime.wait_until = "domcontentloaded"

    storage_path = tmp_path / "auth" / "user.json"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text("{}", encoding="utf-8")

    page = _FakePage(locator_counts={".sensitive": 2})
    context = _FakeContext(page)
    browser = _FakeBrowser([context])
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    outcome = asyncio.run(
        _capture_one(
            cast(Any, browser),
            scenario,
            config=config,
            project_root=tmp_path,
            output_dir=output_dir,
        )
    )

    assert outcome.status == "ok"
    assert outcome.image_path is not None
    assert context.closed is True
    assert browser.new_context_calls
    context_kwargs = browser.new_context_calls[0]
    assert context_kwargs["extra_http_headers"] == {"X-Test": "yes"}
    assert context_kwargs["storage_state"] == str(storage_path)
    assert context.init_scripts and "Math.random" in context.init_scripts[0]
    assert page.wait_for_selector_calls == [("#ready", 12_345)]
    assert page.wait_for_timeout_calls == [250]
    assert page.style_calls == [".ads, .clock { visibility: hidden !important; }"]
    screenshot_call = page.screenshot_calls[0]
    assert screenshot_call["full_page"] is True
    assert screenshot_call["animations"] == "disabled"
    assert screenshot_call["mask"] is not None
    assert len(screenshot_call["mask"]) == 2


def test_capture_one_returns_error_when_storage_state_missing(tmp_path: Path) -> None:
    scenario = _scenario(storage_state="auth/missing.json")
    browser = _FakeBrowser([])
    config = DJVRTConfig(base_url="http://example.test")

    outcome = asyncio.run(
        _capture_one(
            cast(Any, browser),
            scenario,
            config=config,
            project_root=tmp_path,
            output_dir=tmp_path / "out",
        )
    )

    assert outcome.status == "error"
    assert outcome.error is not None
    assert "storage_state not found" in outcome.error
    assert browser.new_context_calls == []


def test_capture_one_returns_error_on_navigation_exception(tmp_path: Path) -> None:
    scenario = _scenario()
    config = DJVRTConfig(base_url="http://example.test")
    page = _FakePage(goto_error=RuntimeError("navigation failed"))
    context = _FakeContext(page)
    browser = _FakeBrowser([context])

    outcome = asyncio.run(
        _capture_one(
            cast(Any, browser),
            scenario,
            config=config,
            project_root=tmp_path,
            output_dir=tmp_path / "out",
        )
    )

    assert outcome.status == "error"
    assert outcome.error == "navigation failed"
    assert context.closed is True


def test_capture_async_returns_empty_for_unmatched_scenario_keys(tmp_path: Path) -> None:
    scenario = _scenario(key="only")
    lockfile = _lockfile(scenario)
    config = DJVRTConfig(base_url="http://example.test")
    output_dir = tmp_path / "captures"

    result = asyncio.run(
        _capture_async(
            lockfile,
            config=config,
            project_root=tmp_path,
            output_dir=output_dir,
            scenario_keys={"different"},
            progress_callback=None,
        )
    )

    assert result == {}
    assert output_dir.exists()


def test_capture_async_uses_progress_callback_and_closes_browser(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scenario_a = _scenario(key="a")
    scenario_b = _scenario(key="b")
    lockfile = _lockfile(scenario_a, scenario_b)
    config = DJVRTConfig(base_url="http://example.test")

    browser = _FakeBrowser([])
    playwright_context = _FakeAsyncPlaywrightContext(_FakePlaywright(browser))
    monkeypatch.setattr("playwright.async_api.async_playwright", lambda: playwright_context)

    async def _fake_capture_one(
        _browser: _FakeBrowser,
        scenario: LockedScenario,
        *,
        config: DJVRTConfig,
        project_root: Path,
        output_dir: Path,
    ) -> CaptureOutcome:
        del config, project_root, output_dir
        await asyncio.sleep(0)
        return CaptureOutcome(key=scenario.key, status="ok", image_path=f"/tmp/{scenario.key}.png")

    monkeypatch.setattr(capture, "_capture_one", _fake_capture_one)

    updates: list[tuple[int, int]] = []
    result = asyncio.run(
        _capture_async(
            lockfile,
            config=config,
            project_root=tmp_path,
            output_dir=tmp_path / "captures",
            scenario_keys=None,
            progress_callback=lambda completed, total: updates.append((completed, total)),
        )
    )

    assert set(result) == {"a", "b"}
    assert updates
    assert updates[-1] == (2, 2)
    assert browser.closed is True


def test_capture_scenarios_wrapper_invokes_async_capture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    scenario = _scenario(key="wrapped")
    lockfile = _lockfile(scenario)
    config = DJVRTConfig(base_url="http://example.test")

    async def _fake_capture_async(*_: Any, **__: Any) -> dict[str, CaptureOutcome]:
        return {"wrapped": CaptureOutcome(key="wrapped", status="ok", image_path="/tmp/wrapped.png")}

    monkeypatch.setattr(capture, "_capture_async", _fake_capture_async)

    result = capture_scenarios(
        lockfile,
        config=config,
        project_root=tmp_path,
        output_dir=tmp_path / "captures",
    )

    assert "wrapped" in result
