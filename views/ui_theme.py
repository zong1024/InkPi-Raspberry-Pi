"""Shared UI theme tokens for the Raspberry Pi touch interface."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication, QLayout

from config import IS_RASPBERRY_PI


THEME = {
    "bg": "#1b1512",
    "bg_alt": "#231b17",
    "surface": "#f3eadc",
    "surface_alt": "#eadbc7",
    "surface_soft": "#f7f1e7",
    "header": "#15100d",
    "header_soft": "#30241d",
    "ink": "#211810",
    "muted": "#76614f",
    "line": "#ccb296",
    "line_strong": "#9d7959",
    "accent": "#bb6a3a",
    "accent_hover": "#a7592b",
    "accent_soft": "#f0d4c0",
    "gold": "#d2a86c",
    "gold_soft": "#f3e2bf",
    "success": "#4f7f5a",
    "success_soft": "#d9eadb",
    "warning": "#b47a33",
    "warning_soft": "#f2e0bc",
    "danger": "#b34b3e",
    "danger_soft": "#f2d1cb",
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
    for candidate in FONT_CANDIDATES:
        match = families.get(candidate.casefold())
        if match:
            _RESOLVED_FONT_FAMILY = match
            return _RESOLVED_FONT_FAMILY

    for font_file in FONT_FILES:
        if not font_file.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id < 0:
            continue
        registered = QFontDatabase.applicationFontFamilies(font_id)
        for family in registered:
            if family.casefold() in {candidate.casefold() for candidate in FONT_CANDIDATES}:
                _RESOLVED_FONT_FAMILY = family
                return _RESOLVED_FONT_FAMILY
        if registered:
            _RESOLVED_FONT_FAMILY = registered[0]
            return _RESOLVED_FONT_FAMILY

    _RESOLVED_FONT_FAMILY = FONT_FAMILY
    return _RESOLVED_FONT_FAMILY


def font_stack() -> str:
    """Return the CSS font-family stack for the active application font."""
    primary = ensure_app_font_family()
    fallbacks = ['"Noto Sans CJK SC"', '"Noto Sans SC"', '"Microsoft YaHei UI"', '"Microsoft YaHei"', '"SimHei"', '"SimSun"', '"PingFang SC"', "sans-serif"]
    quoted_primary = f'"{primary}"'
    ordered = [quoted_primary] + [item for item in fallbacks if item != quoted_primary]
    return ", ".join(ordered)


def score_to_color(score: int) -> str:
    """Return the primary color for a numeric score."""
    if score >= 85:
        return THEME["success"]
    if score >= 60:
        return THEME["warning"]
    return THEME["danger"]


def score_to_soft_color(score: int) -> str:
    """Return a soft background color for a numeric score."""
    if score >= 85:
        return THEME["success_soft"]
    if score >= 60:
        return THEME["warning_soft"]
    return THEME["danger_soft"]


def app_font(size: int, weight: int = int(QFont.Weight.Normal)) -> QFont:
    """Create a font with the shared family, size, and weight."""
    return QFont(ensure_app_font_family(), size, weight)


def clear_layout(layout: QLayout) -> None:
    """Safely remove all child items from a layout."""
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
        background-color: {THEME["bg"]};
    }}

    QFrame#appHeader {{
        background-color: {THEME["header"]};
        border: 1px solid {THEME["header_soft"]};
        border-radius: 20px;
    }}

    QLabel#brandTitle,
    QLabel#headerTitle,
    QLabel#headerClock {{
        background-color: transparent;
        color: #fff8ee;
    }}

    QLabel#brandCaption,
    QLabel#headerSubtitle {{
        background-color: transparent;
        color: #d7c4ae;
    }}

    QLabel#headerPill {{
        background-color: {THEME["accent_soft"]};
        color: {THEME["accent"]};
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 13px;
        padding: 5px 10px;
        font-size: 11px;
        font-weight: 600;
    }}

    QFrame#mainSurface {{
        background-color: {THEME["surface"]};
        border: 1px solid {THEME["line_strong"]};
        border-radius: 26px;
    }}

    QFrame#footerBar {{
        background-color: {THEME["header"]};
        border: 1px solid {THEME["header_soft"]};
        border-radius: 18px;
    }}

    QPushButton#navButton {{
        background-color: transparent;
        color: #ceb8a3;
        border: none;
        border-radius: 16px;
        padding: 9px 14px;
        font-size: 13px;
        font-weight: 700;
    }}

    QPushButton#navButton:hover {{
        background-color: rgba(255, 255, 255, 0.08);
        color: #fff8ee;
    }}

    QPushButton#navButton[active="true"] {{
        background-color: {THEME["accent"]};
        color: #fff9f3;
    }}

    QPushButton {{
        border: none;
        border-radius: 16px;
        padding: 10px 14px;
        font-size: 13px;
        font-weight: 700;
        background-color: {THEME["surface_alt"]};
        color: {THEME["ink"]};
    }}

    QPushButton:hover {{
        background-color: #eadfce;
    }}

    QPushButton:disabled {{
        background-color: #ddd0be;
        color: #aa9680;
    }}

    QPushButton#primaryButton {{
        background-color: {THEME["accent"]};
        color: #fff8f3;
    }}

    QPushButton#primaryButton:hover {{
        background-color: {THEME["accent_hover"]};
    }}

    QPushButton#secondaryButton {{
        background-color: {THEME["surface_soft"]};
        color: {THEME["ink"]};
        border: 1px solid {THEME["line"]};
    }}

    QPushButton#secondaryButton:hover {{
        background-color: #fbf3e7;
    }}

    QPushButton#ghostButton {{
        background-color: rgba(255, 255, 255, 0.02);
        color: {THEME["muted"]};
        border: 1px solid {THEME["line"]};
    }}

    QPushButton#ghostButton:hover {{
        background-color: {THEME["surface_alt"]};
        color: {THEME["ink"]};
    }}

    QPushButton#dangerButton {{
        background-color: {THEME["danger_soft"]};
        color: {THEME["danger"]};
    }}

    QPushButton#dangerButton:hover {{
        background-color: {THEME["danger"]};
        color: #fff7f3;
    }}

    QFrame#panelCard,
    QFrame#heroCard,
    QFrame#statCard,
    QFrame#metricCard,
    QFrame#resultCard,
    QFrame#historyCard,
    QFrame#guideCard,
    QFrame#previewCard,
    QFrame#feedbackCard,
    QFrame#emptyStateCard {{
        background-color: {THEME["surface"]};
        border: 1px solid {THEME["line"]};
        border-radius: 24px;
    }}

    QFrame#heroCard {{
        background-color: #f2e6d6;
        border: 1px solid {THEME["line_strong"]};
    }}

    QFrame#accentCard {{
        background-color: #211711;
        border: 1px solid #49372b;
        border-radius: 24px;
    }}

    QLabel#sectionTitle {{
        color: {THEME["ink"]};
        font-size: 17px;
        font-weight: 700;
    }}

    QLabel#sectionSubtitle,
    QLabel#cardSubtitle,
    QLabel#mutedLabel {{
        color: {THEME["muted"]};
    }}

    QLabel#heroEyebrow,
    QLabel#chipLabel {{
        background-color: {THEME["gold_soft"]};
        color: {THEME["warning"]};
        border-radius: 12px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 600;
    }}

    QLabel#accentChip {{
        background-color: {THEME["accent_soft"]};
        color: {THEME["accent"]};
        border-radius: 12px;
        padding: 5px 10px;
        font-size: 11px;
        font-weight: 600;
    }}

    QLabel#successChip {{
        background-color: {THEME["success_soft"]};
        color: {THEME["success"]};
        border-radius: 12px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 600;
    }}

    QLabel#metricValue {{
        color: {THEME["ink"]};
        font-size: 26px;
        font-weight: 700;
    }}

    QLabel#scoreNumber {{
        color: {THEME["ink"]};
        font-size: 64px;
        font-weight: 800;
    }}

    QLabel#scoreGrade {{
        font-size: 16px;
        font-weight: 700;
    }}

    QLabel#dimensionScore {{
        font-size: 24px;
        font-weight: 700;
    }}

    QLabel#historyScore {{
        font-size: 30px;
        font-weight: 800;
    }}

    QLabel#historyGrade {{
        font-size: 12px;
        font-weight: 700;
    }}

    QFrame#previewFrame {{
        background-color: #110d0b;
        border: 1px solid #4a382c;
        border-radius: 26px;
    }}

    QLabel#previewLabel {{
        background-color: #110d0b;
        color: #f5ebde;
        border-radius: 22px;
        padding: 12px;
    }}

    QLabel#statusPill {{
        background-color: {THEME["surface_alt"]};
        color: {THEME["muted"]};
        border-radius: 12px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 600;
    }}

    QLabel#statusPill[state="ready"] {{
        background-color: {THEME["success_soft"]};
        color: {THEME["success"]};
    }}

    QLabel#statusPill[state="working"] {{
        background-color: {THEME["gold_soft"]};
        color: {THEME["warning"]};
    }}

    QLabel#statusPill[state="error"] {{
        background-color: {THEME["danger_soft"]};
        color: {THEME["danger"]};
    }}

    QLabel#statusPill[state="idle"] {{
        background-color: {THEME["surface_alt"]};
        color: {THEME["muted"]};
    }}

    QComboBox {{
        background-color: {THEME["surface"]};
        border: 1px solid {THEME["line"]};
        border-radius: 14px;
        padding: 8px 12px;
        min-height: 22px;
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QScrollArea {{
        border: none;
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        width: 10px;
        border: none;
        background: transparent;
        margin: 4px;
    }}

    QScrollBar::handle:vertical {{
        background: #ccb7a0;
        border-radius: 5px;
        min-height: 32px;
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
        background-color: #e4d5c2;
        border: 1px solid #dbc7af;
        border-radius: 7px;
        min-height: 12px;
        max-height: 12px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {THEME["accent"]};
        border-radius: 6px;
    }}

    QMessageBox {{
        background-color: {THEME["surface"]};
    }}
    """
