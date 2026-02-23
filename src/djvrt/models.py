from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Viewport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class AuthProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    storage_state: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workers: int = Field(default=4, ge=1, le=32)
    headless: bool = True
    browser_channel: str | None = None
    launch_args: list[str] = Field(default_factory=lambda: ["--no-sandbox"])
    locale: str = "en-US"
    timezone: str = "UTC"
    wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = "networkidle"
    navigation_timeout_ms: int = Field(default=45_000, ge=1)
    settle_time_ms: int = Field(default=500, ge=0)
    default_mismatch_threshold: float = Field(default=0.001, ge=0.0, le=1.0)
    pixel_tolerance: int = Field(default=8, ge=0, le=255)
    default_full_page: bool = True
    default_mask_selectors: list[str] = Field(default_factory=list)
    default_hide_selectors: list[str] = Field(default_factory=list)
    js_random_seed: int | None = Field(default=None, ge=0)


class DiscoveryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_sitemap: bool = True
    sitemap_url: str = "/sitemap.xml"
    use_django_urlconf: bool = True
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=lambda: [r"^/admin", r"^/__debug__"])
    max_urls: int = Field(default=400, ge=1)


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_dir: str = ".djvrt"
    scenario_file: str = ".djvrt/scenarios.json"
    lock_file: str = "djvrt.lock.json"


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    loader: str | None = None
    commands: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None
    phases: list[Literal["discover", "baseline", "check"]] = Field(default_factory=lambda: ["baseline", "check"])
    fail_on_error: bool = True


class ExperimentVariant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    query_params: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)


class DJVRTConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    base_url: str = "http://localhost:8000"
    paths: PathsConfig = Field(default_factory=PathsConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    experiments: list[ExperimentVariant] = Field(default_factory=lambda: [ExperimentVariant(name="control")])
    viewports: list[Viewport] = Field(
        default_factory=lambda: [
            Viewport(name="desktop", width=1440, height=900),
            Viewport(name="mobile", width=390, height=844),
        ]
    )
    auth_profiles: list[AuthProfile] = Field(default_factory=lambda: [AuthProfile(name="anonymous")])

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            msg = "base_url must start with http:// or https://"
            raise ValueError(msg)
        return value.rstrip("/")


class DiscoveredScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    url: str
    tags: list[str] = Field(default_factory=list)
    viewports: list[str] | None = None
    auth_profiles: list[str] | None = None
    experiments: list[str] | None = None
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    wait_for_selector: str | None = None
    wait_for_timeout_ms: int | None = Field(default=None, ge=0)
    mask_selectors: list[str] = Field(default_factory=list)
    hide_selectors: list[str] = Field(default_factory=list)
    full_page: bool | None = None


class LockEnvironment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    python_version: str
    platform: str
    playwright_version: str | None = None


class LockedScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    id: str
    url: str
    tags: list[str] = Field(default_factory=list)
    viewport_name: str
    experiment_name: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    auth_profile: str
    storage_state: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    threshold: float = Field(ge=0.0, le=1.0)
    wait_for_selector: str | None = None
    wait_for_timeout_ms: int
    mask_selectors: list[str] = Field(default_factory=list)
    hide_selectors: list[str] = Field(default_factory=list)
    full_page: bool


class Lockfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lock_version: int = Field(default=1, ge=1)
    generated_at: datetime
    config_digest: str
    environment: LockEnvironment
    scenarios: list[LockedScenario]
    hash: str


class CaptureOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    status: Literal["ok", "error"]
    image_path: str | None = None
    error: str | None = None


class ScenarioResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    id: str
    url: str
    viewport_name: str
    auth_profile: str
    experiment_name: str
    status: Literal[
        "passed",
        "regression",
        "capture_error",
        "baseline_missing",
        "dimension_mismatch",
    ]
    passed: bool
    threshold: float
    mismatch_ratio: float | None = None
    baseline_path: str | None = None
    actual_path: str | None = None
    diff_path: str | None = None
    error: str | None = None


class RunTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    passed: int
    regressions: int
    capture_errors: int
    baseline_missing: int
    dimension_mismatches: int


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    lock_hash: str
    lock_file: str
    mode: Literal["check", "baseline"]
    created_at: datetime
    totals: RunTotals
    results: list[ScenarioResult]
