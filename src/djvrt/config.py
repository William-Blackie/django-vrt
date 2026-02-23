from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import ValidationError

from djvrt.models import DJVRTConfig

DEFAULT_CONFIG_FILENAME = "djvrt.toml"

_DEFAULT_CONFIG_TEXT = """version = 1
base_url = "http://localhost:8000"

[paths]
artifact_dir = ".djvrt"
scenario_file = ".djvrt/scenarios.json"
lock_file = "djvrt.lock.json"

[discovery]
use_sitemap = true
sitemap_url = "/sitemap.xml"
use_django_urlconf = true
include = []
exclude = ["^/admin", "^/__debug__"]
max_urls = 400

[runtime]
workers = 4
headless = true
browser_channel = ""
launch_args = ["--no-sandbox"]
locale = "en-US"
timezone = "UTC"
wait_until = "networkidle"
navigation_timeout_ms = 45000
settle_time_ms = 500
default_mismatch_threshold = 0.001
pixel_tolerance = 8
default_full_page = true
default_mask_selectors = []
default_hide_selectors = []
# Optional: make Math.random deterministic in browser captures.
# js_random_seed = 1337

[data]
enabled = false
loader = ""
commands = []
env = {}
cwd = ""
phases = ["baseline", "check"]
fail_on_error = true

[[experiments]]
name = "control"
query_params = {}
headers = {}

[[viewports]]
name = "desktop"
width = 1440
height = 900

[[viewports]]
name = "mobile"
width = 390
height = 844

[[auth_profiles]]
name = "anonymous"
storage_state = ""
"""


def load_config(path: Path) -> DJVRTConfig:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))

    # Empty strings are easier for humans in TOML than explicit null.
    for auth in raw.get("auth_profiles", []):
        if auth.get("storage_state") == "":
            auth["storage_state"] = None

    runtime = raw.get("runtime", {})
    if runtime.get("browser_channel") == "":
        runtime["browser_channel"] = None

    data = raw.get("data", {})
    if data.get("loader") == "":
        data["loader"] = None
    if data.get("cwd") == "":
        data["cwd"] = None

    try:
        return DJVRTConfig.model_validate(raw)
    except ValidationError as exc:
        msg = f"Invalid config in {path}:\n{exc}"
        raise ValueError(msg) from exc


def write_default_config(path: Path, *, force: bool = False) -> None:
    if path.exists() and not force:
        msg = f"{path} already exists. Pass --force to overwrite."
        raise FileExistsError(msg)
    path.write_text(_DEFAULT_CONFIG_TEXT, encoding="utf-8")


def default_scenarios() -> list[dict[str, object]]:
    return [
        {
            "id": "home",
            "url": "/",
            "tags": ["smoke"],
            "viewports": ["desktop", "mobile"],
            "auth_profiles": ["anonymous"],
        }
    ]
