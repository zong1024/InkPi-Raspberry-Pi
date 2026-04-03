"""Shared UI theme tokens for the 3.5-inch InkPi interface."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication, QLayout

from config import IS_RASPBERRY_PI


THEME = {
    "window": "#F6F1EA",
    "surface": "#FFFDFC",
    "surface_alt": "#F0EAE2",
    "ink": "#2A241F",
    "muted": "#8B8379",
    "line": "#E4DDD4",
    "line_soft": "#EEE7DF",
    "accent": "#B80F1F",
    "accent_hover": "#A10D1B",
    "danger": "#B84E48",
}

FONT_FAMILY = "Noto Sans CJK SC" if IS_RASPBERRY_PI else "Microsoft YaHei UI"
FONT_CANDIDATES = (
    "Noto Sans CJK SC",
    "Noto Sans SC",
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "SimHei",
    "SimSun",
    "Source Han Sans SC",
)
FONT_FILES = (
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyhbd.ttc",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "simhei.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
)
_RESOLVED_FONT_FAMILY: str | None = None
_RESOLVED_ICON_FONT_FAMILY: str | None = None


def ensure_app_font_family() -> str:
    """Resolve and register a usable Simplified Chinese UI font."""
    global _RESOLVED_FONT_FAMILY
    if _RESOLVED_FONT_FAMILY:
        return _RESOLVED_FONT_FAMILY

    if QApplication.instance() is None:
        return FONT_FAMILY

    families = {family.casefold(): family for family in QFontDatabase.families()}
    normalized_candidates = {candidate.casefold() for candidate in FONT_CANDIDATES}

    for candidate in FONT_CANDIDATES:
        match = families.get(candidate.casefold())
        if match:
            _RESOLVED_FONT_FAMILY = match
            return match

    for font_file in FONT_FILES:
        if not font_file.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id < 0:
            continue
        registered = QFontDatabase.applicationFontFamilies(font_id)
        for family in registered:
            if family.casefold() in normalized_candidates:
                _RESOLVED_FONT_FAMILY = family
                return family
        if registered:
            _RESOLVED_FONT_FAMILY = registered[0]
            return registered[0]

    _RESOLVED_FONT_FAMILY = FONT_FAMILY
    return FONT_FAMILY


def font_stack() -> str:
    primary = ensure_app_font_family()
    fallbacks = [
        '"Noto Sans CJK SC"',
        '"Noto Sans SC"',
        '"Microsoft YaHei UI"',
        '"Microsoft YaHei"',
        '"SimHei"',
        '"SimSun"',
        '"PingFang SC"',
        "sans-serif",
    ]
    quoted_primary = f'"{primary}"'
    ordered = [quoted_primary] + [item for item in fallbacks if item != quoted_primary]
    return ", ".join(ordered)


def app_font(size: int, weight: int = int(QFont.Weight.Normal)) -> QFont:
    return QFont(ensure_app_font_family(), size, weight)


def icon_font(size: int, weight: int = int(QFont.Weight.Normal)) -> QFont:
    """Resolve a font with better symbol coverage for lightweight UI icons."""
    global _RESOLVED_ICON_FONT_FAMILY
    if not _RESOLVED_ICON_FONT_FAMILY:
        preferred = (
            "Segoe UI Symbol",
            "Segoe Fluent Icons",
            "Noto Sans Symbols 2",
            "Noto Sans Symbols2",
            "Noto Sans Symbols",
            ensure_app_font_family(),
        )
        if QApplication.instance() is not None:
            families = {family.casefold(): family for family in QFontDatabase.families()}
            for candidate in preferred:
                match = families.get(candidate.casefold())
                if match:
                    _RESOLVED_ICON_FONT_FAMILY = match
                    break
        if not _RESOLVED_ICON_FONT_FAMILY:
            _RESOLVED_ICON_FONT_FAMILY = preferred[-1]
    return QFont(_RESOLVED_ICON_FONT_FAMILY, size, weight)


def clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


def build_stylesheet() -> str:
    stack = font_stack()
    return f"""
    QWidget {{
        font-family: {stack};
        color: {THEME["ink"]};
        background: transparent;
        selection-background-color: {THEME["accent"]};
        selection-color: #ffffff;
    }}

    QMainWindow {{
        background-color: {THEME["window"]};
    }}

    QFrame#mainSurface {{
        background-color: {THEME["window"]};
        border: none;
        border-radius: 0px;
    }}

    QFrame#pageHeader {{
        background: transparent;
        border: none;
        border-radius: 0px;
    }}

    QFrame#scoreCard,
    QFrame#metricPanel,
    QFrame#historyItemCard,
    QFrame#historyGlyphCard,
    QFrame#softCard,
    QLabel#previewLabel {{
        background-color: {THEME["surface"]};
        border: 1px solid {THEME["line"]};
        border-radius: 22px;
    }}

    QFrame#metricPanel,
    QFrame#historyGlyphCard,
    QFrame#softCard {{
        background-color: {THEME["surface_alt"]};
        border-color: {THEME["line_soft"]};
    }}

    QFrame#bottomNav {{
        background-color: {THEME["surface"]};
        border: none;
        border-top: 1px solid {THEME["line"]};
        border-radius: 0px;
    }}

    QLabel#brandTitle {{
        color: {THEME["ink"]};
        font-size: 20px;
        font-weight: 800;
    }}

    QLabel#brandAccent {{
        color: {THEME["accent"]};
        font-size: 28px;
        font-weight: 900;
    }}

    QLabel#pageTitle {{
        color: {THEME["ink"]};
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 1px;
    }}

    QLabel#headlineTitle {{
        color: {THEME["ink"]};
        font-size: 22px;
        font-weight: 800;
    }}

    QLabel#sectionTitle {{
        color: {THEME["ink"]};
        font-size: 13px;
        font-weight: 700;
    }}

    QLabel#sectionSubtitle,
    QLabel#miniLabel {{
        color: {THEME["muted"]};
    }}

    QLabel#miniLabel {{
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
    }}

    QLabel#scoreNumber {{
        color: {THEME["accent"]};
        font-size: 52px;
        font-weight: 900;
    }}

    QLabel#scoreGrade {{
        color: #ffffff;
        background-color: {THEME["accent"]};
        border-radius: 18px;
        padding: 6px 12px;
        font-size: 20px;
        font-weight: 800;
    }}

    QLabel#historyScore {{
        color: {THEME["ink"]};
        font-size: 28px;
        font-weight: 800;
    }}

    QLabel#historyGrade {{
        color: {THEME["accent"]};
        font-size: 18px;
        font-weight: 900;
    }}

    QLabel#glyphLabel {{
        color: {THEME["ink"]};
        font-size: 24px;
        font-weight: 900;
    }}

    QLabel#statusPill {{
        background-color: {THEME["surface_alt"]};
        color: {THEME["muted"]};
        border-radius: 12px;
        padding: 4px 10px;
        font-size: 10px;
        font-weight: 700;
    }}

    QLabel#statusPill[state="ready"] {{
        background-color: #E6F0E9;
        color: #2F7D57;
    }}

    QLabel#statusPill[state="working"] {{
        background-color: #F6E9D8;
        color: #AD742D;
    }}

    QLabel#statusPill[state="error"] {{
        background-color: #F4DFDE;
        color: {THEME["danger"]};
    }}

    QPushButton {{
        border: none;
        border-radius: 20px;
        padding: 8px 14px;
        font-size: 12px;
        font-weight: 700;
        background-color: {THEME["surface_alt"]};
        color: {THEME["ink"]};
    }}

    QPushButton:hover {{
        background-color: #E8E1D9;
    }}

    QPushButton:disabled {{
        background-color: #ECE5DD;
        color: #B3A99E;
    }}

    QPushButton#primaryButton {{
        background-color: {THEME["accent"]};
        color: #ffffff;
        padding-left: 18px;
        padding-right: 18px;
    }}

    QPushButton#primaryButton:hover {{
        background-color: {THEME["accent_hover"]};
    }}

    QPushButton#ghostButton,
    QPushButton#buttonCard {{
        background-color: {THEME["surface_alt"]};
        border: 1px solid {THEME["line_soft"]};
        color: {THEME["ink"]};
        border-radius: 20px;
    }}

    QPushButton#floatingButton {{
        background-color: {THEME["accent"]};
        color: #ffffff;
        border-radius: 26px;
        font-size: 20px;
        font-weight: 900;
    }}

    QPushButton#headerIconButton {{
        background-color: transparent;
        color: {THEME["muted"]};
        border: none;
        font-size: 16px;
        font-weight: 700;
        padding: 0px;
    }}

    QPushButton#navButton {{
        background-color: transparent;
        color: {THEME["muted"]};
        border: none;
        border-radius: 14px;
        padding: 4px 8px;
        font-size: 11px;
        font-weight: 700;
    }}

    QPushButton#navButton[active="true"] {{
        color: {THEME["accent"]};
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}

    QScrollBar:vertical {{
        width: 6px;
        border: none;
        background: transparent;
        margin: 2px;
    }}

    QScrollBar::handle:vertical {{
        background: #D5CCC1;
        border-radius: 3px;
        min-height: 18px;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        border: none;
        background: transparent;
        height: 0px;
    }}

    QProgressBar {{
        background-color: #EAE2D8;
        border: none;
        border-radius: 4px;
        min-height: 8px;
        max-height: 8px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {THEME["accent"]};
        border-radius: 4px;
    }}

    QLabel#previewLabel {{
        background-color: #EFE9E1;
        color: {THEME["muted"]};
        border-radius: 20px;
        padding: 2px;
    }}

    QMessageBox {{
        background-color: {THEME["surface"]};
    }}
    """
