# src/ui/settings_dialog.py
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QWidget,
)


CONFIG_DIR = Path.home() / ".howtocook_organizer"
CONFIG_FILE = CONFIG_DIR / "config.json"

# 翻译提供者列表（内部名称 → 显示标签）
TRANSLATOR_CHOICES = [
    ("claude-code", "Claude Code CLI (本地，默认)"),
    ("openai",      "OpenAI / 兼容 API (DeepSeek 等)"),
    ("anthropic",   "Anthropic API"),
    ("deepl",       "DeepL 翻译平台"),
    ("baidu",       "百度翻译 API (标准版免费)"),
    ("aliyun",      "阿里云机器翻译"),
]

# 每种翻译方式可配置的字段名列表（用于控制可见性和缓存）
PROVIDER_FIELD_MAP: dict[str, list[str]] = {
    "claude-code": [],
    "openai":      ["api_key", "base_url", "model"],
    "anthropic":   ["api_key", "base_url", "model"],
    "deepl":       ["api_key", "base_url"],
    "baidu":       ["baidu_appid", "baidu_secret"],
    "aliyun":      ["aliyun_ak_id", "aliyun_ak_secret"],
}


class SettingsDialog(QDialog):
    """对话框：配置仓库路径和 USDA 翻译设置。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(540)

        layout = QFormLayout(self)

        # ================================================================
        # 仓库路径
        # ================================================================
        repo_group = QGroupBox("仓库路径")
        repo_form = QFormLayout(repo_group)

        source_row = QHBoxLayout()
        self._source_edit = QLineEdit()
        self._source_edit.setPlaceholderText("HowToCook 源仓库路径")
        source_btn = QPushButton("浏览...")
        source_btn.clicked.connect(self._browse_source)
        source_row.addWidget(self._source_edit, 1)
        source_row.addWidget(source_btn)
        repo_form.addRow("源仓库 (HowToCook):", source_row)

        output_row = QHBoxLayout()
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("HowToCook_json 输出仓库路径")
        output_btn = QPushButton("浏览...")
        output_btn.clicked.connect(self._browse_output)
        output_row.addWidget(self._output_edit, 1)
        output_row.addWidget(output_btn)
        repo_form.addRow("输出仓库 (HowToCook_json):", output_row)

        layout.addRow(repo_group)

        # ================================================================
        # USDA 翻译配置
        # ================================================================
        ts_group = QGroupBox("USDA 数据翻译")
        self._ts_form = QFormLayout(ts_group)

        self._ts_combo = QComboBox()
        for name, label in TRANSLATOR_CHOICES:
            self._ts_combo.addItem(label, name)
        self._ts_combo.currentIndexChanged.connect(self._on_ts_changed)
        self._ts_form.addRow("翻译引擎:", self._ts_combo)

        # 通用字段：API Key（OpenAI / Anthropic / DeepL）
        self._ts_api_key = QLineEdit()
        self._ts_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._ts_form.addRow("API Key:", self._ts_api_key)

        # 百度翻译专用字段：APP ID 和密钥
        self._ts_baidu_appid = QLineEdit()
        self._ts_baidu_appid.setPlaceholderText("百度翻译 APP ID")
        self._ts_form.addRow("APP ID:", self._ts_baidu_appid)

        self._ts_baidu_secret = QLineEdit()
        self._ts_baidu_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._ts_baidu_secret.setPlaceholderText("百度翻译密钥")
        self._ts_form.addRow("密钥:", self._ts_baidu_secret)

        # 阿里云机器翻译专用字段：AccessKey ID 和 AccessKey Secret
        self._ts_aliyun_ak_id = QLineEdit()
        self._ts_aliyun_ak_id.setPlaceholderText("AccessKey ID")
        self._ts_form.addRow("AccessKey ID:", self._ts_aliyun_ak_id)

        self._ts_aliyun_ak_secret = QLineEdit()
        self._ts_aliyun_ak_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._ts_aliyun_ak_secret.setPlaceholderText("AccessKey Secret")
        self._ts_form.addRow("AccessKey Secret:", self._ts_aliyun_ak_secret)

        # 通用字段：接口地址
        self._ts_base_url = QLineEdit()
        self._ts_form.addRow("接口地址:", self._ts_base_url)

        # 通用字段：模型
        self._ts_model = QLineEdit()
        self._ts_form.addRow("模型:", self._ts_model)

        layout.addRow(ts_group)

        # 字段名 → widget 映射
        self._field_widgets: dict[str, QLineEdit] = {
            "api_key": self._ts_api_key,
            "baidu_appid": self._ts_baidu_appid,
            "baidu_secret": self._ts_baidu_secret,
            "aliyun_ak_id": self._ts_aliyun_ak_id,
            "aliyun_ak_secret": self._ts_aliyun_ak_secret,
            "base_url": self._ts_base_url,
            "model": self._ts_model,
        }

        # 每种提供商的配置缓存
        self._provider_cache: dict[str, dict[str, str]] = {}
        # 当前选中的提供商（用于检测切换）
        self._current_ts_provider: str | None = None

        # 初始状态
        self._on_ts_changed()

        # ================================================================
        # 按钮
        # ================================================================
        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")
        save_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addRow(btn_row)

    # ------------------------------------------------------------------
    # Public helpers (static)
    # ------------------------------------------------------------------

    @staticmethod
    def load_config() -> dict:
        """从磁盘加载配置。未找到时返回空字典。"""
        if not CONFIG_FILE.exists():
            return {}
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def save_config(config: dict) -> None:
        """持久化 config 字典到配置文件。"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def validate_paths(config: dict) -> tuple[bool, str]:
        """检查 source_dir 和 output_dir 是否有效。"""
        source = config.get("source_dir", "")
        output = config.get("output_dir", "")
        if not source or not output:
            return False, "请设置源仓库路径和输出仓库路径。"
        if not Path(source).is_dir():
            return False, f"源仓库路径无效: {source}"
        if not Path(output).is_dir():
            return False, f"输出仓库路径无效: {output}"
        return True, ""

    @staticmethod
    def get_translator_config() -> dict:
        """获取 USDA 翻译配置（供 usda_import_dialog 使用）。"""
        config = SettingsDialog.load_config()
        ts = config.get("usda_translator", {})
        provider = ts.get("provider", "claude-code")

        # 优先读新格式（per-provider configs）
        configs = ts.get("configs", {})
        if configs:
            pc = configs.get(provider, {})
            if provider == "baidu":
                appid = pc.get("baidu_appid", "")
                secret = pc.get("baidu_secret", "")
                api_key = f"{appid}:{secret}" if appid and secret else ""
            elif provider == "aliyun":
                ak_id = pc.get("aliyun_ak_id", "")
                ak_secret = pc.get("aliyun_ak_secret", "")
                api_key = f"{ak_id}:{ak_secret}" if ak_id and ak_secret else ""
            else:
                api_key = pc.get("api_key", "")
            return {
                "provider": provider,
                "api_key": api_key,
                "base_url": pc.get("base_url", ""),
                "model": pc.get("model", ""),
            }

        # 回退到旧格式（平铺字段）
        if provider == "baidu":
            appid = ts.get("baidu_appid", "")
            secret = ts.get("baidu_secret", "")
            api_key = f"{appid}:{secret}" if appid and secret else ""
        elif provider == "aliyun":
            ak_id = ts.get("aliyun_ak_id", "")
            ak_secret = ts.get("aliyun_ak_secret", "")
            api_key = f"{ak_id}:{ak_secret}" if ak_id and ak_secret else ""
        else:
            api_key = ts.get("api_key", "")
        return {
            "provider": provider,
            "api_key": api_key,
            "base_url": ts.get("base_url", ""),
            "model": ts.get("model", ""),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> dict:
        """返回当前对话框值的配置字典。"""
        # 先保存当前提供商的字段到缓存
        if self._current_ts_provider is not None:
            fields = PROVIDER_FIELD_MAP.get(self._current_ts_provider, [])
            cache: dict[str, str] = {}
            for field_name in fields:
                widget = self._field_widgets[field_name]
                cache[field_name] = widget.text().strip()
            self._provider_cache[self._current_ts_provider] = cache

        return {
            "source_dir": self._source_edit.text().strip(),
            "output_dir": self._output_edit.text().strip(),
            "usda_translator": {
                "provider": self._ts_combo.currentData(),
                "configs": {k: dict(v) for k, v in self._provider_cache.items()},
            },
        }

    def set_config(self, config: dict) -> None:
        """从 config 填充对话框字段。"""
        self._source_edit.setText(config.get("source_dir", ""))
        self._output_edit.setText(config.get("output_dir", ""))

        ts_config = config.get("usda_translator", {})
        provider = ts_config.get("provider", "claude-code")

        # 从配置文件填充提供商缓存
        configs = ts_config.get("configs", {})
        if configs:
            # 新格式：per-provider configs
            self._provider_cache = {}
            for prov_name, prov_cfg in configs.items():
                self._provider_cache[prov_name] = dict(prov_cfg)
        else:
            # 旧格式迁移：将平铺字段按当前提供商提取
            old_fields = {
                "api_key": ts_config.get("api_key", ""),
                "baidu_appid": ts_config.get("baidu_appid", ""),
                "baidu_secret": ts_config.get("baidu_secret", ""),
                "base_url": ts_config.get("base_url", ""),
                "model": ts_config.get("model", ""),
            }
            provider_fields = PROVIDER_FIELD_MAP.get(provider, [])
            self._provider_cache = {
                provider: {f: old_fields.get(f, "") for f in provider_fields},
            }

        # 阻止信号以避免中间状态，手动触发一次完整的切换处理
        self._ts_combo.blockSignals(True)
        for i in range(self._ts_combo.count()):
            if self._ts_combo.itemData(i) == provider:
                self._ts_combo.setCurrentIndex(i)
                break
        self._ts_combo.blockSignals(False)
        self._on_ts_changed()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _browse_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 HowToCook 源仓库")
        if path:
            self._source_edit.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 HowToCook_json 输出仓库")
        if path:
            self._output_edit.setText(path)

    def _on_ts_changed(self) -> None:
        """翻译引擎切换时，保存旧配置、恢复新配置、更新可见性。"""
        provider = self._ts_combo.currentData()

        # ---- 保存旧提供商的字段值到缓存 ----
        if self._current_ts_provider is not None:
            old_fields = PROVIDER_FIELD_MAP.get(self._current_ts_provider, [])
            cache: dict[str, str] = {}
            for field_name in old_fields:
                widget = self._field_widgets[field_name]
                cache[field_name] = widget.text()
            self._provider_cache[self._current_ts_provider] = cache

        # ---- 清空所有字段，然后从缓存恢复新提供商的值 ----
        for widget in self._field_widgets.values():
            widget.setText("")
        cached = self._provider_cache.get(provider, {})
        for field_name, value in cached.items():
            if field_name in self._field_widgets:
                self._field_widgets[field_name].setText(value)

        self._current_ts_provider = provider

        # ---- 可见性：只显示当前提供商需要的字段和标签 ----
        visible_fields = set(PROVIDER_FIELD_MAP.get(provider, []))
        for field_name, widget in self._field_widgets.items():
            visible = field_name in visible_fields
            widget.setVisible(visible)
            # 同时隐藏 QFormLayout 自动创建的标签
            label = self._ts_form.labelForField(widget)
            if label is not None:
                label.setVisible(visible)

        # ---- 占位符文本 ----
        is_claude = provider == "claude-code"
        is_deepl = provider == "deepl"
        is_baidu = provider == "baidu"
        is_aliyun = provider == "aliyun"

        if is_claude:
            self._ts_api_key.setPlaceholderText("Claude Code 本地运行，无需 API Key")
            self._ts_base_url.setPlaceholderText("Claude Code 本地运行，无需设置")
            self._ts_model.setPlaceholderText("Claude Code 本地运行，无需设置")
        elif is_deepl:
            self._ts_api_key.setPlaceholderText("DeepL API Key（必填）")
            self._ts_base_url.setPlaceholderText(
                "https://api-free.deepl.com (免费) 或 https://api.deepl.com (Pro)"
            )
            self._ts_model.setPlaceholderText("DeepL 无需设置模型")
        elif is_baidu:
            self._ts_baidu_appid.setPlaceholderText("百度翻译 APP ID")
            self._ts_baidu_secret.setPlaceholderText("百度翻译密钥")
        elif is_aliyun:
            self._ts_aliyun_ak_id.setPlaceholderText("阿里云 AccessKey ID")
            self._ts_aliyun_ak_secret.setPlaceholderText("阿里云 AccessKey Secret")
        else:
            self._ts_api_key.setPlaceholderText("API Key（必填）")
            self._ts_base_url.setPlaceholderText(
                "自定义地址（如 https://api.deepseek.com/v1，留空用默认）"
            )
            self._ts_model.setPlaceholderText(
                "模型名（如 gpt-4o / deepseek-chat，留空用默认）"
            )

    def _on_save(self) -> None:
        config = self.get_config()
        ok, msg = self.validate_paths(config)
        if not ok:
            QMessageBox.warning(self, "路径无效", msg)
            return
        self.save_config(config)
        self.accept()
