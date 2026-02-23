from pathlib import Path

from PIL import Image

from djvrt.diffing import compare_images


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
