"""验证翻译设置的 per-provider 缓存和标签隐藏功能。"""
import sys
import json
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFormLayout
from src.ui.settings_dialog import (
    SettingsDialog,
    PROVIDER_FIELD_MAP,
    CONFIG_FILE,
)

app = QApplication.instance() or QApplication(sys.argv)


def _visible_info(dlg: SettingsDialog) -> dict[str, tuple[bool, bool]]:
    """返回每个字段的 (widget_visible, label_visible) 状态。"""
    result = {}
    for name, widget in dlg._field_widgets.items():
        label = dlg._ts_form.labelForField(widget)
        result[name] = (widget.isVisible(), label.isVisible() if label else None)
    return result


def test_1_provider_fields_map():
    """PROVIDER_FIELD_MAP 定义与翻译引擎数量一致。"""
    providers = [name for name, _ in SettingsDialog._ts_combo_items]
    # 直接从常量验证
    from src.ui.settings_dialog import TRANSLATOR_CHOICES
    provider_names = [n for n, _ in TRANSLATOR_CHOICES]
    assert set(provider_names) == set(PROVIDER_FIELD_MAP.keys()), \
        f"Mismatch: {set(provider_names)} vs {set(PROVIDER_FIELD_MAP.keys())}"
    print("  ✅ PROVIDER_FIELD_MAP 覆盖所有翻译引擎")


def test_2_initial_visibility():
    """初始状态（Claude Code）所有配置字段和标签都应隐藏。"""
    dlg = SettingsDialog()
    info = _visible_info(dlg)
    for name, (w_vis, l_vis) in info.items():
        assert not w_vis, f"Claude Code 初始状态：{name} widget 应隐藏"
        assert not l_vis, f"Claude Code 初始状态：{name} label 应隐藏"
    print("  ✅ Claude Code 初始状态：所有配置字段和标签均隐藏")


def test_3_switch_preserves_config():
    """切换翻译引擎后，之前引擎的配置值应被缓存，切回时恢复。"""
    dlg = SettingsDialog()

    # 切到 OpenAI，填值
    dlg._ts_combo.setCurrentIndex(1)  # openai
    dlg._ts_api_key.setText("sk-test-openai-key")
    dlg._ts_base_url.setText("https://api.openai.com/v1")
    dlg._ts_model.setText("gpt-4o")

    # 切到 DeepL，填值
    dlg._ts_combo.setCurrentIndex(3)  # deepl
    assert dlg._ts_api_key.text() == "", "切到 DeepL 后 API Key 应为空"
    dlg._ts_api_key.setText("deepl-test-key")
    dlg._ts_base_url.setText("https://api-free.deepl.com")

    # 切到百度，填值
    dlg._ts_combo.setCurrentIndex(4)  # baidu
    dlg._ts_baidu_appid.setText("baidu-appid-123")
    dlg._ts_baidu_secret.setText("baidu-secret-456")

    # 切回 OpenAI
    dlg._ts_combo.setCurrentIndex(1)  # openai
    assert dlg._ts_api_key.text() == "sk-test-openai-key", \
        f"切回 OpenAI 后 API Key 应恢复，实际: '{dlg._ts_api_key.text()}'"
    assert dlg._ts_base_url.text() == "https://api.openai.com/v1", \
        f"切回 OpenAI 后 Base URL 应恢复，实际: '{dlg._ts_base_url.text()}'"
    assert dlg._ts_model.text() == "gpt-4o", \
        f"切回 OpenAI 后 Model 应恢复，实际: '{dlg._ts_model.text()}'"

    # 切回 DeepL
    dlg._ts_combo.setCurrentIndex(3)  # deepl
    assert dlg._ts_api_key.text() == "deepl-test-key", \
        f"切回 DeepL 后 API Key 应恢复，实际: '{dlg._ts_api_key.text()}'"
    assert dlg._ts_base_url.text() == "https://api-free.deepl.com", \
        f"切回 DeepL 后 Base URL 应恢复，实际: '{dlg._ts_base_url.text()}'"

    # 切回百度
    dlg._ts_combo.setCurrentIndex(4)  # baidu
    assert dlg._ts_baidu_appid.text() == "baidu-appid-123", \
        f"切回百度后 APP ID 应恢复，实际: '{dlg._ts_baidu_appid.text()}'"
    assert dlg._ts_baidu_secret.text() == "baidu-secret-456", \
        f"切回百度后密钥应恢复，实际: '{dlg._ts_baidu_secret.text()}'"

    print("  ✅ 切换翻译引擎后配置正确保存和恢复")


def test_4_visibility_per_provider():
    """每种翻译引擎只显示对应的字段和标签。"""
    dlg = SettingsDialog()

    for idx, (prov_name, prov_label) in enumerate(
        [(n, l) for n, l in __import__("src.ui.settings_dialog", fromlist=["TRANSLATOR_CHOICES"]).TRANSLATOR_CHOICES]
    ):
        dlg._ts_combo.setCurrentIndex(idx)
        expected = set(PROVIDER_FIELD_MAP[prov_name])
        info = _visible_info(dlg)
        for fname, (w_vis, l_vis) in info.items():
            should_show = fname in expected
            assert w_vis == should_show, \
                f"[{prov_name}] 字段 {fname} 可见性={w_vis}，期望={should_show}"
            assert l_vis == should_show, \
                f"[{prov_name}] 标签 {fname} 可见性={l_vis}，期望={should_show}"
    print("  ✅ 每种引擎的字段和标签可见性均正确")


def test_5_save_load_new_format():
    """get_config / set_config 新格式（per-provider configs）正确往返。"""
    dlg = SettingsDialog()

    # 配置多个提供商
    dlg._ts_combo.setCurrentIndex(1)  # openai
    dlg._ts_api_key.setText("sk-openai")
    dlg._ts_base_url.setText("https://api.openai.com/v1")
    dlg._ts_model.setText("gpt-4o")

    dlg._ts_combo.setCurrentIndex(3)  # deepl
    dlg._ts_api_key.setText("deepl-key")
    dlg._ts_base_url.setText("https://api.deepl.com")

    dlg._ts_combo.setCurrentIndex(4)  # baidu
    dlg._ts_baidu_appid.setText("myappid")
    dlg._ts_baidu_secret.setText("mysecret")

    # 保存
    config = dlg.get_config()
    usda = config["usda_translator"]
    assert "configs" in usda, "新格式应包含 configs 键"
    assert usda["provider"] == "baidu"
    assert usda["configs"]["openai"]["api_key"] == "sk-openai"
    assert usda["configs"]["deepl"]["api_key"] == "deepl-key"
    assert usda["configs"]["baidu"]["baidu_appid"] == "myappid"

    # 加载到新对话框
    dlg2 = SettingsDialog()
    dlg2.set_config(config)
    assert dlg2._ts_combo.currentData() == "baidu"
    assert dlg2._ts_baidu_appid.text() == "myappid"
    assert dlg2._ts_baidu_secret.text() == "mysecret"

    # 验证缓存中其他提供商也在
    assert dlg2._provider_cache["openai"]["api_key"] == "sk-openai"
    assert dlg2._provider_cache["deepl"]["api_key"] == "deepl-key"

    # 切到 openai 验证恢复
    dlg2._ts_combo.setCurrentIndex(1)
    assert dlg2._ts_api_key.text() == "sk-openai"
    assert dlg2._ts_base_url.text() == "https://api.openai.com/v1"
    assert dlg2._ts_model.text() == "gpt-4o"

    print("  ✅ 新格式配置文件保存和加载正确")


def test_6_old_format_migration():
    """旧格式（平铺字段）加载时正确迁移到 per-provider 缓存。"""
    old_config = {
        "source_dir": "D:\\fake_source",
        "output_dir": "D:\\fake_output",
        "usda_translator": {
            "provider": "openai",
            "api_key": "old-sk-key",
            "base_url": "https://api.old.com",
            "model": "old-model",
        },
    }

    dlg = SettingsDialog()
    dlg.set_config(old_config)

    assert dlg._ts_combo.currentData() == "openai"
    assert dlg._ts_api_key.text() == "old-sk-key"
    assert dlg._ts_base_url.text() == "https://api.old.com"
    assert dlg._ts_model.text() == "old-model"
    print("  ✅ 旧格式配置正确迁移加载")


def test_7_get_translator_config_new_format():
    """get_translator_config() 能正确读取新格式。"""
    # 直接写一个临时配置文件
    import src.ui.settings_dialog as sd_mod

    original_config_file = sd_mod.CONFIG_FILE
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    new_config = {
        "usda_translator": {
            "provider": "deepl",
            "configs": {
                "deepl": {"api_key": "deepl-123", "base_url": "https://api.deepl.com"},
                "baidu": {"baidu_appid": "b-appid", "baidu_secret": "b-secret"},
            },
        },
    }
    json.dump(new_config, tmp)
    tmp.close()

    try:
        sd_mod.CONFIG_FILE = Path(tmp.name)

        # DeepL
        result = SettingsDialog.get_translator_config()
        assert result["provider"] == "deepl"
        assert result["api_key"] == "deepl-123"
        assert result["base_url"] == "https://api.deepl.com"

        # 改为 baidu
        new_config["usda_translator"]["provider"] = "baidu"
        Path(tmp.name).write_text(json.dumps(new_config), encoding="utf-8")
        result = SettingsDialog.get_translator_config()
        assert result["provider"] == "baidu"
        assert result["api_key"] == "b-appid:b-secret"
    finally:
        sd_mod.CONFIG_FILE = original_config_file
        Path(tmp.name).unlink(missing_ok=True)

    print("  ✅ get_translator_config() 新格式读取正确")


def test_8_get_translator_config_old_format():
    """get_translator_config() 能正确读取旧格式（向后兼容）。"""
    import src.ui.settings_dialog as sd_mod

    original_config_file = sd_mod.CONFIG_FILE
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    old_config = {
        "usda_translator": {
            "provider": "openai",
            "api_key": "old-key",
            "base_url": "https://old.api",
            "model": "old-model",
        },
    }
    json.dump(old_config, tmp)
    tmp.close()

    try:
        sd_mod.CONFIG_FILE = Path(tmp.name)
        result = SettingsDialog.get_translator_config()
        assert result["provider"] == "openai"
        assert result["api_key"] == "old-key"
        assert result["base_url"] == "https://old.api"
        assert result["model"] == "old-model"
    finally:
        sd_mod.CONFIG_FILE = original_config_file
        Path(tmp.name).unlink(missing_ok=True)

    print("  ✅ get_translator_config() 旧格式向后兼容读取正确")


if __name__ == "__main__":
    tests = [
        test_1_provider_fields_map,
        test_2_initial_visibility,
        test_3_switch_preserves_config,
        test_4_visibility_per_provider,
        test_5_save_load_new_format,
        test_6_old_format_migration,
        test_7_get_translator_config_new_format,
        test_8_get_translator_config_old_format,
    ]

    passed = 0
    failed = 0
    for test in tests:
        name = test.__doc__.split("。")[0]
        print(f"\n▶ {name}")
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"结果：{passed} 通过，{failed} 失败，共 {len(tests)} 项")
    if failed:
        sys.exit(1)
