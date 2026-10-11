"""見た目（assets/style.css）の単体テスト。

色を差し替えたときに、文字が読めなくなる組み合わせを入れてしまわないための見張り番。
講義の基準どおり、文字と背景のコントラスト比は 4.5:1 以上にする。
（対応：UI再設計方針 4章「配色」、UXハニカム「アクセシブル」）
"""

import re
from pathlib import Path

CSS_PATH = Path(__file__).resolve().parents[2] / "app" / "frontend" / "assets" / "style.css"
CONFIG_PATH = Path(__file__).resolve().parents[2] / ".streamlit" / "config.toml"


def _variables():
    css = CSS_PATH.read_text(encoding="utf-8")
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9A-Fa-f]{6})", css))


def _luminance(hex_color):
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_text_is_readable_on_backgrounds():
    v = _variables()
    for background in ("bg", "surface", "tint"):
        assert _contrast(v["text"], v[background]) >= 4.5, background
    # 補助文字は、背景だけでなくカードの面・淡い面の上にも載る
    for background in ("bg", "surface", "tint"):
        assert _contrast(v["muted"], v[background]) >= 4.5, background


def test_primary_button_text_is_readable():
    v = _variables()
    assert _contrast("#FFFFFF", v["primary"]) >= 4.5
    assert _contrast("#FFFFFF", v["primary-d"]) >= 4.5


def test_primary_color_text_is_readable_on_surfaces():
    """主色は「白い枠のボタンの文字」「選択中のタブの文字」としても使う。面の上で読めるかを見る。"""
    v = _variables()
    for background in ("bg", "surface"):
        assert _contrast(v["primary"], v[background]) >= 4.5, background
        assert _contrast(v["primary-d"], v[background]) >= 4.5, background


def test_config_toml_matches_style_css():
    """色は .streamlit/config.toml と style.css の2か所にある。片方だけ変えて食い違うのを防ぐ。"""
    v = _variables()
    config = CONFIG_PATH.read_text(encoding="utf-8")
    theme = dict(re.findall(r'^(\w+)\s*=\s*"(#[0-9A-Fa-f]{6})"', config, flags=re.MULTILINE))
    expected = {"primaryColor": "primary", "backgroundColor": "bg", "textColor": "text"}
    for config_key, css_name in expected.items():
        assert theme[config_key].lower() == v[css_name].lower(), config_key


def test_reduced_motion_is_respected():
    css = CSS_PATH.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
