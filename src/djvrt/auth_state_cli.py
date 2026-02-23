from __future__ import annotations

import argparse
from pathlib import Path

from djvrt.auth_state import create_form_auth_state


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Playwright storage_state for djvrt.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Application base URL.")
    parser.add_argument("--login-path", default="/accounts/login/", help="Login page path.")
    parser.add_argument("--email", required=True, help="Login email.")
    parser.add_argument("--password", required=True, help="Login password.")
    parser.add_argument(
        "--output",
        default=".djvrt/auth/user.json",
        help="Output path for Playwright storage_state JSON.",
    )
    parser.add_argument("--next-path", default="/", help="Path to open after successful login.")
    parser.add_argument("--timeout-ms", type=int, default=45_000, help="Navigation timeout in ms.")
    parser.add_argument(
        "--email-selector",
        default="input[type='email']",
        help="CSS selector for email input.",
    )
    parser.add_argument(
        "--password-selector",
        default="input[type='password']",
        help="CSS selector for password input.",
    )
    parser.add_argument(
        "--submit-selector",
        default="button[type='submit']",
        help="CSS selector for submit button.",
    )
    parser.add_argument(
        "--wait-until",
        default="domcontentloaded",
        help="Playwright wait_until strategy for login navigation.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = create_form_auth_state(
        base_url=args.base_url,
        login_path=args.login_path,
        email=args.email,
        password=args.password,
        output=Path(args.output).resolve(),
        next_path=args.next_path,
        timeout_ms=args.timeout_ms,
        email_selector=args.email_selector,
        password_selector=args.password_selector,
        submit_selector=args.submit_selector,
        wait_until=args.wait_until,
    )
    print(f"Wrote auth storage_state: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
