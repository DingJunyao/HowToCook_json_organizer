# src/ui/usda_import_dialog.py
"""USDA 数据导入对话框 — 后台执行构建脚本并显示实时进度。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QMessageBox,
)


class _BuildWorker(QThread):
    """后台线程：执行 scripts/build_usda_data.py。"""

    progress_line = Signal(str)
    translate_progress = Signal(int, int)
    finished = Signal(bool, str)  # success, message

    def __init__(self, skip_download: bool = False, skip_translate: bool = False):
        super().__init__()
        self._skip_download = skip_download
        self._skip_translate = skip_translate

    def run(self) -> None:
        import subprocess

        script_path = (
            Path(__file__).resolve().parent.parent.parent
            / "scripts" / "build_usda_data.py"
        )

        cmd = [sys.executable, str(script_path)]
        if self._skip_download:
            cmd.append("--skip-download")
        if self._skip_translate:
            cmd.append("--skip-translate")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            for line in proc.stdout:
                line_stripped = line.rstrip("\n\r")
                if line_stripped:
                    self.progress_line.emit(line_stripped)
                    # 检测翻译进度
                    if line_stripped.startswith("[TRANSLATE] 批次"):
                        parts = line_stripped.split()
                        try:
                            batch_str = parts[1]  # "1/45"
                            current, total = batch_str.split("/")
                            self.translate_progress.emit(int(current), int(total))
                        except (IndexError, ValueError):
                            pass

            proc.wait()

            if proc.returncode == 0:
                self.finished.emit(True, "USDA 数据构建完成！")
            else:
                self.finished.emit(False, f"脚本退出码: {proc.returncode}")

        except FileNotFoundError:
            self.finished.emit(False, f"找不到 Python 解释器: {sys.executable}")
        except Exception as e:
            self.finished.emit(False, f"运行出错: {e}")


class USDAImportDialog(QDialog):
    """USDA 数据导入进度对话框。

    用法:
        dlg = USDAImportDialog(parent=self)
        dlg.set_nutrition_matcher_callback(self._nm.load_data)
        dlg.exec()
    """

    def __init__(
        self,
        parent=None,
        *,
        skip_download: bool = False,
        skip_translate: bool = False,
    ):
        super().__init__(parent)
        self.setWindowTitle("导入 USDA 营养数据")
        self.setMinimumSize(600, 480)

        self._worker: _BuildWorker | None = None
        self._finished_success: bool | None = None
        self._on_data_ready_cb: callable | None = None

        layout = QVBoxLayout(self)

        # 说明文字
        self._desc_label = QLabel(
            "将从 USDA FoodData Central 下载营养数据并使用 AI 翻译为中文。\n"
            "此操作需要网络连接，大约需要 10-30 分钟（取决于翻译批次数量）。"
        )
        self._desc_label.setWordWrap(True)
        layout.addWidget(self._desc_label)

        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("准备中...")
        layout.addWidget(self._progress_bar)

        # 日志输出
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setStyleSheet("font-family: 'Consolas', 'Courier New', monospace; font-size: 12px;")
        layout.addWidget(self._log_view, 1)

        # 按钮
        self._close_btn = QPushButton("关闭")
        self._close_btn.clicked.connect(self._on_close)
        self._close_btn.setEnabled(False)
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self._on_cancel)

        from PySide6.QtWidgets import QHBoxLayout
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

    def set_on_data_ready(self, callback: callable) -> None:
        """设置数据就绪后的回调（用于重新加载 NutritionMatcher）。"""
        self._on_data_ready_cb = callback

    def start(self) -> None:
        """启动构建流程。"""
        self._log_view.clear()
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("启动中...")
        self._cancel_btn.setEnabled(True)
        self._close_btn.setEnabled(False)
        self._finished_success = None

        self._worker = _BuildWorker()
        self._worker.progress_line.connect(self._on_progress_line)
        self._worker.translate_progress.connect(self._on_translate_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    # ---- callback ------------------------------------------------------------

    def set_nutrition_matcher_callback(self, callback: callable) -> None:
        """(兼容旧 API) 设置数据就绪后的回调。"""
        self._on_data_ready_cb = callback

    # ---- internal ------------------------------------------------------------

    def _on_progress_line(self, line: str) -> None:
        """追加日志行，滚动到底部。"""
        bar = self._log_view.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 10

        self._log_view.append(line)
        if at_bottom:
            bar.setValue(bar.maximum())

        # 根据行内容更新进度条
        if "[STEP]" in line:
            # 粗略估算进度
            if "下载" in line or "准备" in line:
                self._progress_bar.setValue(5)
                self._progress_bar.setFormat("下载数据...")
            elif "提取" in line:
                self._progress_bar.setValue(15)
                self._progress_bar.setFormat("提取营养素...")
            elif "翻译" in line:
                self._progress_bar.setValue(25)
                self._progress_bar.setFormat("AI 翻译中...")
            elif "合并" in line:
                self._progress_bar.setValue(90)
                self._progress_bar.setFormat("合并去重...")
            elif "写入" in line:
                self._progress_bar.setValue(95)
                self._progress_bar.setFormat("写入文件...")
        elif "[OK]" in line:
            self._progress_bar.setValue(100)
            self._progress_bar.setFormat("完成!")
        elif "[ERROR]" in line:
            self._progress_bar.setFormat("出错")

    def _on_translate_progress(self, current: int, total: int) -> None:
        """更新翻译进度条 (25% ~ 85%)。"""
        if total > 0:
            pct = 25 + int((current / total) * 60)
            self._progress_bar.setValue(pct)
            self._progress_bar.setFormat(f"AI 翻译中... {current}/{total}")

    def _on_finished(self, success: bool, message: str) -> None:
        """构建完成。"""
        self._finished_success = success
        self._cancel_btn.setEnabled(False)
        self._close_btn.setEnabled(True)
        self._close_btn.setText("关闭")

        if success:
            self._progress_bar.setValue(100)
            self._progress_bar.setFormat("✓ 完成!")
            self._log_view.append(f"\n✓ {message}")

            # 触发回调重新加载数据
            if self._on_data_ready_cb:
                try:
                    self._on_data_ready_cb()
                except Exception as e:
                    self._log_view.append(f"⚠ 重新加载数据失败: {e}")
        else:
            self._progress_bar.setFormat("✗ 失败")
            self._log_view.append(f"\n✗ {message}")
            self._close_btn.setText("关闭")

    def _on_cancel(self) -> None:
        """取消构建。"""
        if self._worker and self._worker.isRunning():
            result = QMessageBox.question(
                self,
                "确认取消",
                "确定要取消吗？已完成的工作将丢失。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if result == QMessageBox.StandardButton.Yes:
                self._worker.terminate()
                self._worker.wait(3000)
                self._log_view.append("\n[INFO] 已取消")
                self._progress_bar.setFormat("已取消")
                self._cancel_btn.setEnabled(False)
                self._close_btn.setEnabled(True)

    def _on_close(self) -> None:
        """关闭对话框。"""
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "正在运行", "请等待任务完成或先取消。")
            return
        self.accept()


# ============================================================================
# 独立的导入启动函数（供 main.py 调用）
# ============================================================================


def open_usda_import(
    parent,
    on_data_ready: callable | None = None,
    *,
    skip_download: bool = False,
    skip_translate: bool = False,
) -> USDAImportDialog:
    """打开 USDA 数据导入对话框并启动构建流程。

    如果 data/usda_nutrition.json 已存在，提示用户是否重新构建。

    Args:
        parent: 父窗口
        on_data_ready: 数据就绪后回调（用于重新加载 NutritionMatcher）
        skip_download: 跳过下载
        skip_translate: 跳过翻译

    Returns:
        USDAImportDialog 实例
    """
    # 检查是否已有数据
    existing = (
        Path(__file__).resolve().parent.parent.parent / "data" / "usda_nutrition.json"
    )
    if existing.exists():
        size_mb = existing.stat().st_size / 1048576
        result = QMessageBox.question(
            parent,
            "数据已存在",
            f"USDA 营养数据库已存在 ({size_mb:.1f} MB)。\n\n"
            "是否重新构建？（这将重新下载和翻译全部数据）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            # 用户取消重新构建，但数据已存在，仍然触发回调
            if on_data_ready:
                on_data_ready()
            return None

    dlg = USDAImportDialog(
        parent,
        skip_download=skip_download,
        skip_translate=skip_translate,
    )
    if on_data_ready:
        dlg.set_on_data_ready(on_data_ready)
    dlg.start()
    return dlg
