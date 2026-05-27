# src/managers/image_manager.py
from __future__ import annotations

import hashlib
import logging
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ImageManager:
    """管理菜谱图片的导入、去重、命名和清理。"""

    IMAGES_DIR_NAME = "images"

    @staticmethod
    def ensure_images_dir(output_dir: Path) -> Path:
        """确保 out/images 目录存在并返回其路径。"""
        images_dir = output_dir / "out" / ImageManager.IMAGES_DIR_NAME
        images_dir.mkdir(parents=True, exist_ok=True)
        return images_dir

    @staticmethod
    def resolve_image_path(md_image_url: str, md_source_path: str, source_dir: Path) -> Optional[Path]:
        """将 MD 中的图片 URL/路径解析为实际文件系统路径。

        - 如果 URL 是网络地址 (http/https)，下载到临时文件并返回路径。
        - 以 / 开头: 相对于 source_dir 的绝对路径。
        - 其他: 相对于 MD 文件所在目录的相对路径（需先拼接到 source_dir 下）。
        文件不存在/下载失败时返回 None。
        """
        if md_image_url.startswith(("http://", "https://")):
            return ImageManager._download_remote_image(md_image_url)

        if md_image_url.startswith("/"):
            base = source_dir
            candidate = base / md_image_url.lstrip("/")
        else:
            # md_source_path is relative to source_dir; resolve full MD path first
            md_full = source_dir / md_source_path
            md_dir = md_full.parent
            candidate = md_dir / md_image_url

        candidate = candidate.resolve()
        if candidate.is_file():
            return candidate
        return None

    @staticmethod
    def _download_remote_image(url: str) -> Optional[Path]:
        """下载远程图片到临时文件，返回临时文件路径。失败返回 None。"""
        try:
            # 从 URL 中提取文件扩展名
            ext = Path(url.split("?")[0]).suffix or ".jpg"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    shutil.copyfileobj(resp, tmp)
                return Path(tmp.name)
        except Exception as e:
            logger.warning("下载远程图片失败 %s: %s", url, e)
            return None

    @staticmethod
    def compute_hash(file_path: Path) -> str:
        """计算文件的 SHA256 哈希值。"""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _get_existing_hashes(self, images_dir: Path, recipe_name: str) -> dict[str, str]:
        """扫描 images_dir 中属于当前菜谱的图片，建立 hash → relative_path 映射。"""
        hash_map: dict[str, str] = {}
        if not images_dir.is_dir():
            return hash_map
        prefix = f"{recipe_name}_"
        for f in images_dir.iterdir():
            if f.is_file() and f.name.startswith(prefix):
                hash_map[self.compute_hash(f)] = f"images/{f.name}"
        return hash_map

    def _get_next_index(self, images_dir: Path, recipe_name: str, existing_images: list[str]) -> int:
        """获取下一个可用的图片序号。

        从 existing_images 和 images_dir 中已有的 {recipe_name}_N 文件名中提取最大序号。
        """
        max_idx = -1
        pattern = re.compile(re.escape(recipe_name) + r"_(\d+)(?:\.\w+)?$")

        for img_path in existing_images:
            name = Path(img_path).stem  # e.g. "水煮鱼_0"
            m = pattern.search(name)
            if m:
                max_idx = max(max_idx, int(m.group(1)))

        if images_dir.is_dir():
            for f in images_dir.iterdir():
                if f.is_file():
                    m = pattern.search(f.name)
                    if m:
                        max_idx = max(max_idx, int(m.group(1)))

        return max_idx + 1

    def _image_full_path(self, output_dir: Path, img_path: str) -> Path:
        """计算图片在输出目录中的完整文件系统路径。"""
        if Path(img_path).is_absolute():
            return Path(img_path)
        return output_dir / "out" / img_path

    def _build_existing_file_hashes(self, existing_images: list[str], output_dir: Path) -> dict[str, str]:
        """对 existing_images 中存在文件的条目计算 hash，返回 {hash: relative_path}。"""
        result = {}
        for img_path in existing_images:
            full = self._image_full_path(output_dir, img_path)
            if full.is_file():
                h = self.compute_hash(full)
                result[h] = img_path
        return result

    def _clean_existing_images(self, existing_images: list[str], output_dir: Path) -> list[str]:
        """清理 existing_images 中对应文件不存在的条目。"""
        cleaned = []
        for img_path in existing_images:
            full = self._image_full_path(output_dir, img_path)
            if full.is_file():
                cleaned.append(img_path)
        return cleaned

    def import_images(
        self,
        recipe_name: str,
        md_image_urls: list[str],
        md_source_path: str,
        source_dir: Path,
        output_dir: Path,
        existing_images: list[str],
    ) -> tuple[list[str], list[str]]:
        """导入 MD 图片到 out/images，智能合并到现有图片列表。

        流程:
        1. 清理 existing_images 中文件不存在的条目
        2. 建立现有文件的 hash→路径映射
        3. 对每个 MD 图片:
           - 解析实际文件路径
           - 通过 hash 检查是否已存在
           - 已存在则复用路径，否则复制并重命名
        4. 新图片追加到清理后的现有图片列表末尾

        返回: (最终图片列表, 新增的图片路径列表)
        """
        images_dir = self.ensure_images_dir(output_dir)

        # Step 1: clean existing images
        cleaned = self._clean_existing_images(existing_images, output_dir)

        # Step 2: build hash map from existing images in out/images
        existing_hash_map = self._build_existing_file_hashes(cleaned, output_dir)

        # Step 3: also add hashes from files in images_dir that match recipe_name
        dir_hash_map = self._get_existing_hashes(images_dir, recipe_name)
        # merge: prefer relative path from existing_images
        all_existing_hashes = {**dir_hash_map, **existing_hash_map}

        new_images: list[str] = []
        next_idx = self._get_next_index(images_dir, recipe_name, cleaned)

        for url in md_image_urls:
            src_path = self.resolve_image_path(url, md_source_path, source_dir)
            if src_path is None:
                continue

            src_hash = self.compute_hash(src_path)

            if src_hash in all_existing_hashes:
                # Already exists, reuse the existing path
                existing_path = all_existing_hashes[src_hash]
                if existing_path not in cleaned:
                    cleaned.append(existing_path)
                # else: already in cleaned, skip (no duplicate)
            else:
                # Copy with naming convention
                ext = src_path.suffix or ".jpg"
                new_name = f"{recipe_name}_{next_idx}{ext}"
                dest = images_dir / new_name
                shutil.copy2(src_path, dest)
                rel_path = f"images/{new_name}"
                cleaned.append(rel_path)
                new_images.append(rel_path)
                all_existing_hashes[src_hash] = rel_path
                next_idx += 1

        return cleaned, new_images

    # 常见图片扩展名，锚定 extract_image_urls 的匹配边界
    _IMAGE_EXT_PATTERN = r"(?:png|PNG|jpg|JPG|jpeg|JPEG|gif|GIF|webp|WEBP|bmp|BMP|svg|SVG|ico|ICO|tiff|TIFF|tif|TIF)"

    @staticmethod
    def extract_image_urls(markdown_content: str) -> list[str]:
        """从 Markdown 内容中提取所有图片链接。

        使用括号计数扫描而非纯正则，支持文件名中含括号的路径（如 ./血浆鸭(特辣).jpg）
        以及带查询参数的 URL（如 https://example.com/img.jpg?w=800），
        同时不会贪婪吞掉行内后续内容。
        """
        urls: list[str] = []
        pos = 0
        content_len = len(markdown_content)

        while pos < content_len:
            # Find ![
            bang_br = markdown_content.find("![", pos)
            if bang_br == -1:
                break
            # Find ]( after ![
            alt_end = markdown_content.find("](", bang_br + 2)
            if alt_end == -1:
                pos = bang_br + 2
                continue

            # Scan for balanced parentheses after ](
            url_start = alt_end + 2
            depth = 1
            scan = url_start
            while scan < content_len and depth > 0:
                ch = markdown_content[scan]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                scan += 1

            if depth == 0:
                # scan points one past the matching )
                url = markdown_content[url_start:scan - 1]
                urls.append(url)
                pos = scan
            else:
                # Unmatched, skip this
                pos = url_start

        return urls
