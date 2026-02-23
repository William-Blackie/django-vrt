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
        generated_at="2026-01-01T00:00:00Z",
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
        generated_at="2026-01-01T00:00:00Z",
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
