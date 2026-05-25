# tests/test_image_manager.py
"""Unit tests for ImageManager."""
import hashlib
from pathlib import Path

import pytest

from src.managers.image_manager import ImageManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_env(tmp_path):
    """Create a temp directory with source MD file, images, and output dir."""
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (output / "out").mkdir()

    # Create sample images
    images_dir = source / "dishes" / "meat_dish" / "images"
    images_dir.mkdir(parents=True)
    img1 = images_dir / "step1.jpg"
    img2 = images_dir / "step2.png"
    img1.write_bytes(b"fake_image_data_1")
    img2.write_bytes(b"fake_image_data_2")

    # Write sample MD with image links
    md_path = source / "dishes" / "meat_dish" / "水煮鱼.md"
    md_path.write_text(
        "# 水煮鱼的做法\n\n"
        "![步骤1](images/step1.jpg)\n"
        "![步骤2](images/step2.png)\n"
        "![网络图片](https://example.com/remote.jpg)\n\n"
        "## 操作\n\n1. 做鱼。\n",
        encoding="utf-8",
    )

    return source, output, md_path, img1, img2


# ---------------------------------------------------------------------------
# 1. extract_image_urls
# ---------------------------------------------------------------------------


def test_extract_image_urls():
    md = (
        "# 菜谱\n"
        "![步骤1](images/step1.jpg)\n"
        "![步骤2](../images/step2.png)\n"
        "普通文本\n"
        "[链接](http://example.com)\n"
    )
    urls = ImageManager.extract_image_urls(md)
    assert len(urls) == 2
    assert "images/step1.jpg" in urls
    assert "../images/step2.png" in urls


def test_extract_image_urls_empty():
    assert ImageManager.extract_image_urls("# 菜谱\n\n没有图片。") == []


# ---------------------------------------------------------------------------
# 2. compute_hash
# ---------------------------------------------------------------------------


def test_compute_hash(tmp_path):
    f = tmp_path / "test.bin"
    f.write_bytes(b"hello")
    h = ImageManager.compute_hash(f)
    expected = hashlib.sha256(b"hello").hexdigest()
    assert h == expected


def test_compute_hash_same_content(tmp_path):
    f1 = tmp_path / "a.bin"
    f2 = tmp_path / "b.bin"
    f1.write_bytes(b"same")
    f2.write_bytes(b"same")
    assert ImageManager.compute_hash(f1) == ImageManager.compute_hash(f2)


def test_compute_hash_different_content(tmp_path):
    f1 = tmp_path / "a.bin"
    f2 = tmp_path / "b.bin"
    f1.write_bytes(b"data1")
    f2.write_bytes(b"data2")
    assert ImageManager.compute_hash(f1) != ImageManager.compute_hash(f2)


# ---------------------------------------------------------------------------
# 3. resolve_image_path
# ---------------------------------------------------------------------------


def test_resolve_relative_path(tmp_env):
    source, output, md_path, img1, img2 = tmp_env
    url = "images/step1.jpg"
    result = ImageManager.resolve_image_path(url, str(md_path), source)
    assert result is not None
    assert result.resolve() == img1.resolve()


def test_resolve_absolute_path(tmp_env):
    source, output, md_path, img1, img2 = tmp_env
    # Absolute path from source root
    url = "/dishes/meat_dish/images/step2.png"
    result = ImageManager.resolve_image_path(url, str(md_path), source)
    assert result is not None
    assert result.resolve() == img2.resolve()


def test_resolve_http_url():
    result = ImageManager.resolve_image_path("https://example.com/img.jpg", "test.md", Path("/tmp"))
    assert result is None


def test_resolve_nonexistent_file(tmp_env):
    source, output, md_path, img1, img2 = tmp_env
    result = ImageManager.resolve_image_path("images/nonexistent.jpg", str(md_path), source)
    assert result is None


# ---------------------------------------------------------------------------
# 4. ensure_images_dir
# ---------------------------------------------------------------------------


def test_ensure_images_dir(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    result = ImageManager.ensure_images_dir(output)
    assert result.exists()
    assert result.name == "images"


def test_ensure_images_dir_already_exists(tmp_path):
    output = tmp_path / "output"
    (output / "out" / "images").mkdir(parents=True)
    result = ImageManager.ensure_images_dir(output)
    assert result.exists()


# ---------------------------------------------------------------------------
# 5. import_images — full workflow
# ---------------------------------------------------------------------------


def test_import_images_basic(tmp_env):
    source, output, md_path, img1, img2 = tmp_env
    im = ImageManager()

    final_images, new_images = im.import_images(
        recipe_name="水煮鱼",
        md_image_urls=["images/step1.jpg", "images/step2.png"],
        md_source_path=str(md_path),
        source_dir=source,
        output_dir=output,
        existing_images=[],
    )

    assert len(final_images) == 2
    assert len(new_images) == 2
    # Check naming convention
    assert "images/水煮鱼_0.jpg" in final_images
    assert "images/水煮鱼_1.png" in final_images
    # Check files were copied
    assert (output / "out" / "images" / "水煮鱼_0.jpg").exists()
    assert (output / "out" / "images" / "水煮鱼_1.png").exists()


def test_import_images_dedup_by_hash(tmp_env):
    """Importing the same images twice should not duplicate."""
    source, output, md_path, img1, img2 = tmp_env
    im = ImageManager()

    # First import
    final1, new1 = im.import_images(
        recipe_name="水煮鱼",
        md_image_urls=["images/step1.jpg"],
        md_source_path=str(md_path),
        source_dir=source,
        output_dir=output,
        existing_images=[],
    )
    assert len(new1) == 1

    # Second import with same image — should reuse existing
    final2, new2 = im.import_images(
        recipe_name="水煮鱼",
        md_image_urls=["images/step1.jpg"],
        md_source_path=str(md_path),
        source_dir=source,
        output_dir=output,
        existing_images=final1,
    )
    assert len(new2) == 0  # no new images
    assert len(final2) == 1


def test_import_images_cleans_nonexistent(tmp_env):
    """Existing image entries with missing files should be removed."""
    source, output, md_path, img1, img2 = tmp_env
    im = ImageManager()

    # Existing images with one nonexistent file and one that exists but has different content
    (output / "out" / "images").mkdir(parents=True)
    (output / "out" / "images" / "水煮鱼_0.jpg").write_bytes(b"existing_different_content")
    existing = ["images/nonexistent.jpg", "images/水煮鱼_0.jpg"]

    final_images, new_images = im.import_images(
        recipe_name="水煮鱼",
        md_image_urls=["images/step1.jpg"],
        md_source_path=str(md_path),
        source_dir=source,
        output_dir=output,
        existing_images=existing,
    )

    # The nonexistent one should be cleaned; existing valid one kept; new one added
    assert "images/nonexistent.jpg" not in final_images
    assert "images/水煮鱼_0.jpg" in final_images  # valid existing kept
    assert len(new_images) == 1  # one new image added


def test_import_images_smart_merge(tmp_env):
    """New images should be appended after existing valid images."""
    source, output, md_path, img1, img2 = tmp_env
    im = ImageManager()

    # Create an existing image with different content than MD images
    (output / "out" / "images").mkdir(parents=True)
    (output / "out" / "images" / "水煮鱼_0.jpg").write_bytes(b"existing_different_image")
    existing = ["images/水煮鱼_0.jpg"]

    final_images, new_images = im.import_images(
        recipe_name="水煮鱼",
        md_image_urls=["images/step1.jpg", "images/step2.png"],
        md_source_path=str(md_path),
        source_dir=source,
        output_dir=output,
        existing_images=existing,
    )

    assert len(final_images) == 3  # 1 existing + 2 new
    assert final_images[0] == "images/水煮鱼_0.jpg"  # existing first
    assert len(new_images) == 2  # two new ones appended


def test_import_images_dedup_same_content(tmp_env):
    """当 existing_images 中的图片与 MD 图片内容相同时，应复用路径而非新增。"""
    source, output, md_path, img1, img2 = tmp_env
    im = ImageManager()

    # 将 existing 中的图片内容与 MD 中的 step1.jpg 设为相同
    (output / "out" / "images").mkdir(parents=True)
    (output / "out" / "images" / "水煮鱼_0.jpg").write_bytes(img1.read_bytes())
    existing = ["images/水煮鱼_0.jpg"]

    final_images, new_images = im.import_images(
        recipe_name="水煮鱼",
        md_image_urls=["images/step1.jpg"],
        md_source_path=str(md_path),
        source_dir=source,
        output_dir=output,
        existing_images=existing,
    )

    assert len(final_images) == 1
    assert len(new_images) == 0  # 无新增，复用了 existing 路径
    assert "images/水煮鱼_0.jpg" in final_images


def test_import_images_skips_http(tmp_env):
    """HTTP URLs should be skipped."""
    source, output, md_path, img1, img2 = tmp_env
    im = ImageManager()

    final_images, new_images = im.import_images(
        recipe_name="水煮鱼",
        md_image_urls=["https://example.com/remote.jpg", "images/step1.jpg"],
        md_source_path=str(md_path),
        source_dir=source,
        output_dir=output,
        existing_images=[],
    )

    assert len(final_images) == 1
    assert len(new_images) == 1


def test_import_images_next_index_increment(tmp_env):
    """New images should get incrementing indices after existing ones."""
    source, output, md_path, img1, img2 = tmp_env
    im = ImageManager()

    # Create images with indices 0, 1, 3 (gap at 2)
    (output / "out" / "images").mkdir(parents=True)
    (output / "out" / "images" / "水煮鱼_0.jpg").write_bytes(b"a")
    (output / "out" / "images" / "水煮鱼_1.jpg").write_bytes(b"b")
    (output / "out" / "images" / "水煮鱼_3.jpg").write_bytes(b"c")
    existing = ["images/水煮鱼_0.jpg", "images/水煮鱼_1.jpg", "images/水煮鱼_3.jpg"]

    final_images, new_images = im.import_images(
        recipe_name="水煮鱼",
        md_image_urls=["images/step1.jpg"],
        md_source_path=str(md_path),
        source_dir=source,
        output_dir=output,
        existing_images=existing,
    )

    # Next index should be 4
    assert any("水煮鱼_4" in p for p in new_images)
