from datetime import datetime
from pathlib import Path

from PIL import Image

from djvrt.diffing import compare_against_baseline, compare_images
from djvrt.models import (
    CaptureOutcome,
    LockedScenario,
    LockEnvironment,
    Lockfile,
)


def _create_png(path: Path, color: tuple[int, int, int]) -> None:
    image = Image.new("RGB", (10, 10), color=color)
    image.save(path)


def _scenario(*, key: str, scenario_id: str) -> LockedScenario:
    return LockedScenario(
        key=key,
        id=scenario_id,
        url=f"http://example.test/{scenario_id}",
        viewport_name="desktop",
        experiment_name="control",
        width=100,
        height=100,
        auth_profile="anonymous",
        storage_state=None,
        headers={},
        threshold=0.001,
        wait_for_selector=None,
        wait_for_timeout_ms=0,
        full_page=True,
    )


def _lockfile_with_scenarios(scenarios: list[LockedScenario]) -> Lockfile:
    return Lockfile(
        lock_version=1,
        generated_at=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        config_digest="digest",
        environment=LockEnvironment(
            python_version="3.12",
            platform="test-platform",
            playwright_version="1.0.0",
        ),
        scenarios=scenarios,
        hash="hash1234",
    )


def test_compare_images_identical(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"

    _create_png(baseline, (255, 255, 255))
    _create_png(actual, (255, 255, 255))

    mismatch, same_dimensions = compare_images(
        baseline,
        actual,
        diff_path=diff,
        pixel_tolerance=0,
    )

    assert same_dimensions is True
    assert mismatch == 0.0
    assert diff.exists()


def test_compare_images_detects_change(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"

    _create_png(baseline, (255, 255, 255))
    _create_png(actual, (255, 255, 255))

    image = Image.open(actual)
    image.putpixel((0, 0), (0, 0, 0))
    image.save(actual)

    mismatch, same_dimensions = compare_images(
        baseline,
        actual,
        diff_path=diff,
        pixel_tolerance=0,
    )

    assert same_dimensions is True
    assert mismatch > 0.0
    assert diff.exists()


def test_compare_images_skips_diff_render_for_passing_threshold(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"

    _create_png(baseline, (255, 255, 255))
    _create_png(actual, (255, 255, 255))

    mismatch, same_dimensions = compare_images(
        baseline,
        actual,
        diff_path=diff,
        pixel_tolerance=0,
        diff_threshold=0.001,
    )

    assert same_dimensions is True
    assert mismatch == 0.0
    assert diff.exists() is False


def test_compare_images_returns_dimension_mismatch(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"

    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(baseline)
    Image.new("RGB", (12, 10), color=(255, 255, 255)).save(actual)

    mismatch, same_dimensions = compare_images(
        baseline,
        actual,
        diff_path=diff,
        pixel_tolerance=0,
    )

    assert same_dimensions is False
    assert mismatch == 1.0
    assert diff.exists() is False


def test_compare_against_baseline_only_recompares_selected_keys(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    actual_dir = tmp_path / "actual"
    diff_dir = tmp_path / "diff"
    baseline_dir.mkdir()
    actual_dir.mkdir()

    _create_png(baseline_dir / "one--desktop--anonymous--control--key1.png", (255, 255, 255))
    _create_png(baseline_dir / "two--desktop--anonymous--control--key2.png", (255, 255, 255))
    _create_png(actual_dir / "one--desktop--anonymous--control--key1.png", (255, 255, 255))
    _create_png(actual_dir / "two--desktop--anonymous--control--key2.png", (0, 0, 0))

    lockfile = Lockfile(
        lock_version=1,
        generated_at=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        config_digest="digest",
        environment=LockEnvironment(
            python_version="3.12",
            platform="test-platform",
            playwright_version="1.0.0",
        ),
        scenarios=[
            LockedScenario(
                key="key1",
                id="one",
                url="http://example.test/one",
                viewport_name="desktop",
                experiment_name="control",
                width=100,
                height=100,
                auth_profile="anonymous",
                storage_state=None,
                headers={},
                threshold=0.001,
                wait_for_selector=None,
                wait_for_timeout_ms=0,
                full_page=True,
            ),
            LockedScenario(
                key="key2",
                id="two",
                url="http://example.test/two",
                viewport_name="desktop",
                experiment_name="control",
                width=100,
                height=100,
                auth_profile="anonymous",
                storage_state=None,
                headers={},
                threshold=0.001,
                wait_for_selector=None,
                wait_for_timeout_ms=0,
                full_page=True,
            ),
        ],
        hash="hash1234",
    )

    captures = {
        "key1": CaptureOutcome(
            key="key1",
            status="ok",
            image_path=str(actual_dir / "one--desktop--anonymous--control--key1.png"),
        ),
        "key2": CaptureOutcome(
            key="key2",
            status="ok",
            image_path=str(actual_dir / "two--desktop--anonymous--control--key2.png"),
        ),
    }

    results = compare_against_baseline(
        lockfile,
        captures=captures,
        baseline_dir=baseline_dir,
        diff_dir=diff_dir,
        pixel_tolerance=0,
        scenario_keys={"key1"},
    )

    assert len(results) == 1
    assert results[0].key == "key1"
    assert results[0].status == "passed"
    assert results[0].diff_path is None


def test_compare_against_baseline_parallel_workers_keep_order(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    actual_dir = tmp_path / "actual"
    diff_dir = tmp_path / "diff"
    baseline_dir.mkdir()
    actual_dir.mkdir()

    _create_png(baseline_dir / "a--desktop--anonymous--control--k1.png", (255, 255, 255))
    _create_png(baseline_dir / "b--desktop--anonymous--control--k2.png", (255, 255, 255))
    _create_png(actual_dir / "a--desktop--anonymous--control--k1.png", (255, 255, 255))
    _create_png(actual_dir / "b--desktop--anonymous--control--k2.png", (0, 0, 0))

    lockfile = Lockfile(
        lock_version=1,
        generated_at=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        config_digest="digest",
        environment=LockEnvironment(
            python_version="3.12",
            platform="test-platform",
            playwright_version="1.0.0",
        ),
        scenarios=[
            LockedScenario(
                key="k1",
                id="a",
                url="http://example.test/a",
                viewport_name="desktop",
                experiment_name="control",
                width=100,
                height=100,
                auth_profile="anonymous",
                storage_state=None,
                headers={},
                threshold=0.001,
                wait_for_selector=None,
                wait_for_timeout_ms=0,
                full_page=True,
            ),
            LockedScenario(
                key="k2",
                id="b",
                url="http://example.test/b",
                viewport_name="desktop",
                experiment_name="control",
                width=100,
                height=100,
                auth_profile="anonymous",
                storage_state=None,
                headers={},
                threshold=0.001,
                wait_for_selector=None,
                wait_for_timeout_ms=0,
                full_page=True,
            ),
        ],
        hash="hash1234",
    )

    captures = {
        "k1": CaptureOutcome(
            key="k1",
            status="ok",
            image_path=str(actual_dir / "a--desktop--anonymous--control--k1.png"),
        ),
        "k2": CaptureOutcome(
            key="k2",
            status="ok",
            image_path=str(actual_dir / "b--desktop--anonymous--control--k2.png"),
        ),
    }

    results = compare_against_baseline(
        lockfile,
        captures=captures,
        baseline_dir=baseline_dir,
        diff_dir=diff_dir,
        pixel_tolerance=0,
        workers=2,
    )

    assert [result.key for result in results] == ["k1", "k2"]


def test_compare_against_baseline_can_always_write_diff_images(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    actual_dir = tmp_path / "actual"
    diff_dir = tmp_path / "diff"
    baseline_dir.mkdir()
    actual_dir.mkdir()

    _create_png(baseline_dir / "a--desktop--anonymous--control--k1.png", (255, 255, 255))
    _create_png(actual_dir / "a--desktop--anonymous--control--k1.png", (255, 255, 255))

    lockfile = Lockfile(
        lock_version=1,
        generated_at=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        config_digest="digest",
        environment=LockEnvironment(
            python_version="3.12",
            platform="test-platform",
            playwright_version="1.0.0",
        ),
        scenarios=[
            LockedScenario(
                key="k1",
                id="a",
                url="http://example.test/a",
                viewport_name="desktop",
                experiment_name="control",
                width=100,
                height=100,
                auth_profile="anonymous",
                storage_state=None,
                headers={},
                threshold=0.001,
                wait_for_selector=None,
                wait_for_timeout_ms=0,
                full_page=True,
            ),
        ],
        hash="hash1234",
    )

    captures = {
        "k1": CaptureOutcome(
            key="k1",
            status="ok",
            image_path=str(actual_dir / "a--desktop--anonymous--control--k1.png"),
        ),
    }

    results = compare_against_baseline(
        lockfile,
        captures=captures,
        baseline_dir=baseline_dir,
        diff_dir=diff_dir,
        pixel_tolerance=0,
        always_write_diff_images=True,
    )

    assert len(results) == 1
    assert results[0].status == "passed"
    assert results[0].diff_path is not None
    assert Path(results[0].diff_path).exists()


def test_compare_against_baseline_returns_capture_error_without_capture(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    diff_dir = tmp_path / "diff"
    baseline_dir.mkdir()

    lockfile = _lockfile_with_scenarios([_scenario(key="k1", scenario_id="a")])
    results = compare_against_baseline(
        lockfile,
        captures={},
        baseline_dir=baseline_dir,
        diff_dir=diff_dir,
        pixel_tolerance=0,
    )

    assert len(results) == 1
    assert results[0].status == "capture_error"
    assert results[0].error == "No capture result for scenario"


def test_compare_against_baseline_returns_capture_error_from_failed_capture(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    diff_dir = tmp_path / "diff"
    baseline_dir.mkdir()

    lockfile = _lockfile_with_scenarios([_scenario(key="k1", scenario_id="a")])
    results = compare_against_baseline(
        lockfile,
        captures={"k1": CaptureOutcome(key="k1", status="error", error="capture failed")},
        baseline_dir=baseline_dir,
        diff_dir=diff_dir,
        pixel_tolerance=0,
    )

    assert len(results) == 1
    assert results[0].status == "capture_error"
    assert results[0].error == "capture failed"


def test_compare_against_baseline_returns_baseline_missing(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    actual_dir = tmp_path / "actual"
    diff_dir = tmp_path / "diff"
    baseline_dir.mkdir()
    actual_dir.mkdir()
    image_path = actual_dir / "a--desktop--anonymous--control--k1.png"
    _create_png(image_path, (255, 255, 255))

    lockfile = _lockfile_with_scenarios([_scenario(key="k1", scenario_id="a")])
    results = compare_against_baseline(
        lockfile,
        captures={"k1": CaptureOutcome(key="k1", status="ok", image_path=str(image_path))},
        baseline_dir=baseline_dir,
        diff_dir=diff_dir,
        pixel_tolerance=0,
    )

    assert len(results) == 1
    assert results[0].status == "baseline_missing"
    assert results[0].error == "Baseline image not found"


def test_compare_against_baseline_dimension_mismatch_writes_composite(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    actual_dir = tmp_path / "actual"
    diff_dir = tmp_path / "diff"
    baseline_dir.mkdir()
    actual_dir.mkdir()

    baseline_image = baseline_dir / "a--desktop--anonymous--control--k1.png"
    actual_image = actual_dir / "a--desktop--anonymous--control--k1.png"
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(baseline_image)
    Image.new("RGB", (12, 10), color=(0, 0, 0)).save(actual_image)

    lockfile = _lockfile_with_scenarios([_scenario(key="k1", scenario_id="a")])
    results = compare_against_baseline(
        lockfile,
        captures={"k1": CaptureOutcome(key="k1", status="ok", image_path=str(actual_image))},
        baseline_dir=baseline_dir,
        diff_dir=diff_dir,
        pixel_tolerance=0,
    )

    assert len(results) == 1
    assert results[0].status == "dimension_mismatch"
    assert results[0].diff_path is not None
    assert Path(results[0].diff_path).exists()


def test_compare_against_baseline_returns_empty_for_filtered_out_scenarios(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    diff_dir = tmp_path / "diff"
    baseline_dir.mkdir()

    lockfile = _lockfile_with_scenarios([_scenario(key="k1", scenario_id="a")])
    results = compare_against_baseline(
        lockfile,
        captures={},
        baseline_dir=baseline_dir,
        diff_dir=diff_dir,
        pixel_tolerance=0,
        scenario_keys={"does-not-exist"},
    )
    assert results == []
