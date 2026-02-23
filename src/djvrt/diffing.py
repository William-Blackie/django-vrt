from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops

from djvrt.capture import image_filename
from djvrt.models import CaptureOutcome, LockedScenario, Lockfile, ScenarioResult


def _write_dimension_mismatch_diff(
    baseline_path: Path,
    actual_path: Path,
    diff_path: Path,
) -> None:
    with Image.open(baseline_path) as baseline_image, Image.open(actual_path) as actual_image:
        width = baseline_image.width + actual_image.width
        height = max(baseline_image.height, actual_image.height)
        composite = Image.new("RGB", (width, height), color=(32, 32, 32))
        composite.paste(baseline_image.convert("RGB"), (0, 0))
        composite.paste(actual_image.convert("RGB"), (baseline_image.width, 0))
        composite.save(diff_path)


def compare_images(
    baseline_path: Path,
    actual_path: Path,
    *,
    diff_path: Path,
    pixel_tolerance: int,
    diff_threshold: float | None = None,
) -> tuple[float, bool]:
    with Image.open(baseline_path) as baseline, Image.open(actual_path) as actual:
        if baseline.size != actual.size:
            return 1.0, False

        diff = ImageChops.difference(baseline.convert("RGBA"), actual.convert("RGBA"))
        grayscale = diff.convert("L")

        histogram = grayscale.histogram()
        changed_pixels = sum(histogram[pixel_tolerance + 1 :])
        total_pixels = sum(histogram)
        mismatch_ratio = changed_pixels / total_pixels if total_pixels else 0.0

        should_render_diff = diff_threshold is None or mismatch_ratio > diff_threshold
        if should_render_diff:
            mask = grayscale.point(lambda value: 255 if value > pixel_tolerance else 0)
            actual_rgba = actual.convert("RGBA")
            red_overlay = Image.new("RGBA", actual_rgba.size, (255, 0, 0, 110))
            transparent = Image.new("RGBA", actual_rgba.size, (0, 0, 0, 0))
            highlight = Image.composite(red_overlay, transparent, mask)
            rendered = Image.alpha_composite(actual_rgba, highlight)
            rendered.save(diff_path)

    return mismatch_ratio, True


def _build_capture_error_result(scenario: LockedScenario, error: str | None) -> ScenarioResult:
    return ScenarioResult(
        key=scenario.key,
        id=scenario.id,
        url=scenario.url,
        viewport_name=scenario.viewport_name,
        auth_profile=scenario.auth_profile,
        experiment_name=scenario.experiment_name,
        status="capture_error",
        passed=False,
        threshold=scenario.threshold,
        error=error,
    )


def _build_baseline_missing_result(
    scenario: LockedScenario,
    *,
    actual_path: str | None,
    baseline_path: Path,
) -> ScenarioResult:
    return ScenarioResult(
        key=scenario.key,
        id=scenario.id,
        url=scenario.url,
        viewport_name=scenario.viewport_name,
        auth_profile=scenario.auth_profile,
        experiment_name=scenario.experiment_name,
        status="baseline_missing",
        passed=False,
        threshold=scenario.threshold,
        actual_path=actual_path,
        baseline_path=str(baseline_path),
        error="Baseline image not found",
    )


def compare_against_baseline(
    lockfile: Lockfile,
    *,
    captures: dict[str, CaptureOutcome],
    baseline_dir: Path,
    diff_dir: Path,
    pixel_tolerance: int,
    scenario_keys: set[str] | None = None,
) -> list[ScenarioResult]:
    diff_dir.mkdir(parents=True, exist_ok=True)

    results: list[ScenarioResult] = []
    scenarios = (
        lockfile.scenarios
        if scenario_keys is None
        else [scenario for scenario in lockfile.scenarios if scenario.key in scenario_keys]
    )

    for scenario in scenarios:
        capture = captures.get(scenario.key)
        if capture is None or capture.status != "ok" or capture.image_path is None:
            error = capture.error if capture else "No capture result for scenario"
            results.append(_build_capture_error_result(scenario, error))
            continue

        baseline_path = baseline_dir / image_filename(scenario)
        actual_path = Path(capture.image_path)
        diff_path = diff_dir / image_filename(scenario)

        if not baseline_path.exists():
            results.append(
                _build_baseline_missing_result(
                    scenario,
                    actual_path=str(actual_path),
                    baseline_path=baseline_path,
                )
            )
            continue

        mismatch_ratio, same_dimensions = compare_images(
            baseline_path,
            actual_path,
            diff_path=diff_path,
            pixel_tolerance=pixel_tolerance,
            diff_threshold=scenario.threshold,
        )

        if not same_dimensions:
            _write_dimension_mismatch_diff(baseline_path, actual_path, diff_path)
            results.append(
                ScenarioResult(
                    key=scenario.key,
                    id=scenario.id,
                    url=scenario.url,
                    viewport_name=scenario.viewport_name,
                    auth_profile=scenario.auth_profile,
                    experiment_name=scenario.experiment_name,
                    status="dimension_mismatch",
                    passed=False,
                    threshold=scenario.threshold,
                    mismatch_ratio=1.0,
                    baseline_path=str(baseline_path),
                    actual_path=str(actual_path),
                    diff_path=str(diff_path),
                    error="Image dimensions differ",
                )
            )
            continue

        passed = mismatch_ratio <= scenario.threshold
        status = "passed" if passed else "regression"

        results.append(
            ScenarioResult(
                key=scenario.key,
                id=scenario.id,
                url=scenario.url,
                viewport_name=scenario.viewport_name,
                auth_profile=scenario.auth_profile,
                experiment_name=scenario.experiment_name,
                status=status,
                passed=passed,
                threshold=scenario.threshold,
                mismatch_ratio=mismatch_ratio,
                baseline_path=str(baseline_path),
                actual_path=str(actual_path),
                diff_path=str(diff_path),
            )
        )

    return results
