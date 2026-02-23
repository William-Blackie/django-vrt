from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def _join_url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def create_form_auth_state(
    *,
    base_url: str,
    login_path: str,
    email: str,
    password: str,
    output: Path,
    next_path: str,
    timeout_ms: int,
    email_selector: str,
    password_selector: str,
    submit_selector: str,
    wait_until: str,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)

    login_url = _join_url(base_url, login_path)
    next_url = _join_url(base_url, next_path)
    login_fragment = login_path.strip("/")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(login_url, wait_until=wait_until, timeout=timeout_ms)
            page.fill(email_selector, email)
            page.fill(password_selector, password)
            page.click(submit_selector)
            page.wait_for_load_state("networkidle", timeout=timeout_ms)

            current_url = page.url
            if login_fragment and login_fragment in current_url:
                msg = "Login did not complete. Check credentials and selectors."
                raise RuntimeError(msg)

            if "/two-factor/" in current_url:
                msg = "User hit 2FA flow. Use a user without 2FA for deterministic CI."
                raise RuntimeError(msg)

            page.goto(next_url, wait_until="networkidle", timeout=timeout_ms)
            context.storage_state(path=str(output))
        except PlaywrightTimeoutError as exc:
            msg = f"Timed out while creating auth state at {login_url}"
            raise RuntimeError(msg) from exc
        finally:
            context.close()
            browser.close()

    return output
