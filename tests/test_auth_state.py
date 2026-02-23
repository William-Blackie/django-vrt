from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any

import pytest

import djvrt.auth_state as auth_state
from djvrt.auth_state import _join_url, create_form_auth_state


class _FakePage:
    def __init__(
        self,
        *,
        current_url: str,
        post_login_url: str,
        timeout_exc: type[Exception] | None = None,
        timeout_on_first_goto: bool = False,
    ) -> None:
        self.url = current_url
        self._post_login_url = post_login_url
        self._timeout_exc = timeout_exc
        self._timeout_on_first_goto = timeout_on_first_goto
        self.goto_calls: list[tuple[str, str, int]] = []
        self.fill_calls: list[tuple[str, str]] = []
        self.click_calls: list[str] = []
        self.wait_calls: list[tuple[str, int]] = []

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append((url, wait_until, timeout))
        if self._timeout_on_first_goto and len(self.goto_calls) == 1 and self._timeout_exc is not None:
            raise self._timeout_exc("timed out")
        if len(self.goto_calls) == 1:
            self.url = self._post_login_url
        else:
            self.url = url

    def fill(self, selector: str, value: str) -> None:
        self.fill_calls.append((selector, value))

    def click(self, selector: str) -> None:
        self.click_calls.append(selector)

    def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        self.wait_calls.append((state, timeout))


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.storage_state_path: str | None = None
        self.closed = False

    def new_page(self) -> _FakePage:
        return self._page

    def storage_state(self, *, path: str) -> None:
        self.storage_state_path = path

    def close(self) -> None:
        self.closed = True


class _FakeBrowser:
    def __init__(self, context: _FakeContext) -> None:
        self._context = context
        self.closed = False
        self.launch_called = False

    def new_context(self) -> _FakeContext:
        return self._context

    def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser) -> None:
        self._browser = browser
        self.launch_kwargs: dict[str, Any] | None = None

    def launch(self, *, headless: bool, args: list[str]) -> _FakeBrowser:
        self.launch_kwargs = {"headless": headless, "args": args}
        self._browser.launch_called = True
        return self._browser


class _FakePlaywright:
    def __init__(self, browser: _FakeBrowser) -> None:
        self.chromium = _FakeChromium(browser)


class _FakePlaywrightManager:
    def __init__(self, playwright: _FakePlaywright) -> None:
        self._playwright = playwright

    def __enter__(self) -> _FakePlaywright:
        return self._playwright

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb


def _install_fake_playwright(
    monkeypatch: pytest.MonkeyPatch,
    *,
    page: _FakePage,
) -> tuple[_FakeContext, _FakeBrowser]:
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    manager = _FakePlaywrightManager(_FakePlaywright(browser))
    monkeypatch.setattr(auth_state, "sync_playwright", lambda: manager)
    return context, browser


def test_join_url_normalizes_slashes() -> None:
    assert _join_url("http://example.test", "/accounts/login/") == "http://example.test/accounts/login/"
    assert _join_url("http://example.test/", "dashboard/") == "http://example.test/dashboard/"


def test_create_form_auth_state_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    page = _FakePage(
        current_url="http://example.test/accounts/login/",
        post_login_url="http://example.test/dashboard/",
    )
    context, browser = _install_fake_playwright(monkeypatch, page=page)

    output = tmp_path / "auth" / "user.json"
    result = create_form_auth_state(
        base_url="http://example.test",
        login_path="/accounts/login/",
        email="person@example.test",
        password="secret",
        output=output,
        next_path="/dashboard/",
        timeout_ms=5_000,
        email_selector="#email",
        password_selector="#password",
        submit_selector="#submit",
        wait_until="domcontentloaded",
    )

    assert result == output
    assert output.parent.exists()
    assert context.storage_state_path == str(output)
    assert context.closed is True
    assert browser.closed is True
    assert page.fill_calls == [("#email", "person@example.test"), ("#password", "secret")]
    assert page.click_calls == ["#submit"]
    assert page.goto_calls[0][0] == "http://example.test/accounts/login/"
    assert page.goto_calls[1][0] == "http://example.test/dashboard/"


def test_create_form_auth_state_rejects_login_still_on_login_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    page = _FakePage(
        current_url="http://example.test/accounts/login/",
        post_login_url="http://example.test/accounts/login/?next=/",
    )
    context, browser = _install_fake_playwright(monkeypatch, page=page)

    with pytest.raises(RuntimeError, match="Login did not complete"):
        create_form_auth_state(
            base_url="http://example.test",
            login_path="/accounts/login/",
            email="person@example.test",
            password="secret",
            output=tmp_path / "auth" / "user.json",
            next_path="/",
            timeout_ms=5_000,
            email_selector="#email",
            password_selector="#password",
            submit_selector="#submit",
            wait_until="networkidle",
        )

    assert context.closed is True
    assert browser.closed is True


def test_create_form_auth_state_rejects_two_factor_flow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    page = _FakePage(
        current_url="http://example.test/accounts/login/",
        post_login_url="http://example.test/two-factor/challenge/",
    )
    _install_fake_playwright(monkeypatch, page=page)

    with pytest.raises(RuntimeError, match="2FA flow"):
        create_form_auth_state(
            base_url="http://example.test",
            login_path="/accounts/login/",
            email="person@example.test",
            password="secret",
            output=tmp_path / "auth" / "user.json",
            next_path="/",
            timeout_ms=5_000,
            email_selector="#email",
            password_selector="#password",
            submit_selector="#submit",
            wait_until="load",
        )


def test_create_form_auth_state_wraps_playwright_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class _FakeTimeoutError(Exception):
        pass

    monkeypatch.setattr(auth_state, "PlaywrightTimeoutError", _FakeTimeoutError)
    page = _FakePage(
        current_url="http://example.test/accounts/login/",
        post_login_url="http://example.test/accounts/login/",
        timeout_exc=_FakeTimeoutError,
        timeout_on_first_goto=True,
    )
    _install_fake_playwright(monkeypatch, page=page)

    with pytest.raises(RuntimeError, match="Timed out while creating auth state"):
        create_form_auth_state(
            base_url="http://example.test",
            login_path="/accounts/login/",
            email="person@example.test",
            password="secret",
            output=tmp_path / "auth" / "user.json",
            next_path="/",
            timeout_ms=5_000,
            email_selector="#email",
            password_selector="#password",
            submit_selector="#submit",
            wait_until="commit",
        )
