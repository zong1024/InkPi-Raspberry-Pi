"""Shared UI theme tokens for the 3.5-inch InkPi interface."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication, QLayout

from config import IS_RASPBERRY_PI


THEME = {
    "window": "#f5f1ea",
    "surface": "#fffdfa",
    "surface_alt": "#f1ece5",
    "surface_soft": "#ece6df",
    "ink": "#26211d",
    "muted": "#8c857d",
    "line": "#e2dbd1",
    "line_soft": "#efe9e1",
    "accent": "#b90f1f",
    "accent_hover": "#a20d1b",
    "accent_soft": "#f7d8dc",
    "success": "#2f7d57",
    "warning": "#ba7a28",
    "danger": "#b74b48",
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
    """Return the CSS font-family stack for the active application font."""
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


def score_to_color(score: int) -> str:
    if score >= 85:
        return THEME["accent"]
    if score >= 70:
        return THEME["warning"]
    return THEME["danger"]


def score_to_soft_color(score: int) -> str:
    if score >= 85:
        return "#f7d8dc"
    if score >= 70:
        return "#f5ead7"
    return "#f3dede"


def app_font(size: int, weight: int = int(QFont.Weight.Normal)) -> QFont:
    return QFont(ensure_app_font_family(), size, weight)


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
    """Build the shared application stylesheet."""
    stack = font_stack()
    return f"""
    QWidget {{
        font-family: {stack};
        color: {THEME["ink"]};
        background-color: transparent;
        selection-background-color: {THEME["accent"]};
        selection-color: #ffffff;
    }}

    QMainWindow {{
        background-color: {THEME["window"]};
    }}

    QFrame#mainSurface {{
        background-color: {THEME["surface"]};
        border: 1px solid {THEME["line_soft"]};
        border-radius: 12px;
    }}

    QFrame#topBar,
    QFrame#bottomNav,
    QFrame#panelCard,
    QFrame#heroCard,
    QFrame#statCard,
    QFrame#metricCard,
    QFrame#resultCard,
    QFrame#historyCard,
    QFrame#guideCard,
    QFrame#previewCard,
    QFrame#feedbackCard,
    QFrame#emptyStateCard,
    QFrame#scoreCard,
    QFrame#dimensionBarCard,
    QFrame#historyItemCard,
    QFrame#historyGlyphCard,
    QFrame#softCard {{
        background-color: {THEME["surface"]};
        border: 1px solid {THEME["line"]};
        border-radius: 12px;
    }}

    QFrame#heroCard {{
        background-color: transparent;
        border: none;
    }}

    QFrame#softCard,
    QFrame#historyGlyphCard,
    QFrame#dimensionBarCard {{
        background-color: {THEME["surface_alt"]};
        border: 1px solid {THEME["line_soft"]};
        border-radius: 10px;
    }}

    QLabel#brandTitle {{
        color: {THEME["ink"]};
        font-size: 22px;
        font-weight: 800;
    }}

    QLabel#pageTitle {{
        color: {THEME["ink"]};
        font-size: 17px;
        font-weight: 800;
    }}

    QLabel#sectionTitle {{
        color: {THEME["ink"]};
        font-size: 14px;
        font-weight: 700;
    }}

    QLabel#sectionSubtitle,
    QLabel#mutedLabel,
    QLabel#cardSubtitle {{
        color: {THEME["muted"]};
    }}

    QLabel#brandAccent,
    QLabel#accentText {{
        color: {THEME["accent"]};
        font-weight: 800;
    }}

    QLabel#scoreNumber {{
        color: {THEME["accent"]};
        font-size: 46px;
        font-weight: 900;
    }}

    QLabel#scoreGrade {{
        color: {THEME["accent"]};
        font-size: 18px;
        font-weight: 800;
    }}

    QLabel#historyScore {{
        color: {THEME["accent"]};
        font-size: 26px;
        font-weight: 800;
    }}

    QLabel#historyGrade {{
        color: {THEME["accent"]};
        font-size: 16px;
        font-weight: 800;
    }}

    QLabel#miniLabel {{
        color: {THEME["muted"]};
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 1px;
    }}

    QLabel#glyphLabel {{
        color: {THEME["ink"]};
        font-size: 28px;
        font-weight: 800;
    }}

    QLabel#pillLabel {{
        background-color: {THEME["accent_soft"]};
        color: {THEME["accent"]};
        border-radius: 12px;
        padding: 3px 10px;
        font-size: 10px;
        font-weight: 700;
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
        background-color: #e6f1ea;
        color: {THEME["success"]};
    }}

    QLabel#statusPill[state="working"] {{
        background-color: #f5ead7;
        color: {THEME["warning"]};
    }}

    QLabel#statusPill[state="error"] {{
        background-color: #f3dede;
        color: {THEME["danger"]};
    }}

    QPushButton {{
        border: none;
        border-radius: 10px;
        padding: 5px 10px;
        font-size: 13px;
        font-weight: 700;
        background-color: {THEME["surface_alt"]};
        color: {THEME["ink"]};
    }}

    QPushButton:hover {{
        background-color: #e9e3dc;
    }}

    QPushButton:disabled {{
        background-color: #e7e0d8;
        color: #b2aaa1;
    }}

    QPushButton#primaryButton {{
        background-color: {THEME["accent"]};
        color: #ffffff;
    }}

    QPushButton#primaryButton:hover {{
        background-color: {THEME["accent_hover"]};
    }}

    QPushButton#secondaryButton {{
        background-color: {THEME["surface_alt"]};
        color: {THEME["ink"]};
    }}

    QPushButton#ghostButton {{
        background-color: transparent;
        color: {THEME["ink"]};
        border: 1px solid {THEME["line"]};
    }}

    QPushButton#circleButton {{
        background-color: {THEME["accent"]};
        color: #ffffff;
        border-radius: 17px;
        font-size: 18px;
        font-weight: 900;
    }}

    QPushButton#navButton {{
        background-color: transparent;
        color: {THEME["muted"]};
        border: none;
        border-radius: 14px;
        padding: 6px 8px;
        font-size: 11px;
        font-weight: 700;
    }}

    QPushButton#navButton[active="true"] {{
        color: {THEME["accent"]};
    }}

    QScrollArea {{
        border: none;
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        width: 8px;
        border: none;
        background: transparent;
        margin: 2px;
    }}

    QScrollBar::handle:vertical {{
        background: #cdc5bb;
        border-radius: 4px;
        min-height: 24px;
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
        background-color: #e9e1d8;
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

    QComboBox {{
        background-color: {THEME["surface_alt"]};
        border: 1px solid {THEME["line"]};
        border-radius: 14px;
        padding: 6px 10px;
        min-height: 24px;
    }}

    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}

    QLabel#previewLabel {{
        background-color: #ebe5dd;
        color: {THEME["muted"]};
        border: 1px solid {THEME["line"]};
        border-radius: 22px;
        padding: 8px;
    }}

    QMessageBox {{
        background-color: {THEME["surface"]};
    }}
    """
