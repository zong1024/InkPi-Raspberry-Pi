"""Shared UI theme tokens for the Raspberry Pi touch interface."""

from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLayout

from config import IS_RASPBERRY_PI


THEME = {
    "bg": "#efe6d8",
    "bg_alt": "#f7f0e5",
    "surface": "#fffaf1",
    "surface_alt": "#f4eadb",
    "header": "#261b16",
    "header_soft": "#3a2a23",
    "ink": "#221913",
    "muted": "#7c6657",
    "line": "#d8c4ae",
    "accent": "#b44d35",
    "accent_hover": "#9e3f29",
    "accent_soft": "#edd4cb",
    "gold": "#c9a15f",
    "gold_soft": "#f3e2bf",
    "success": "#567858",
    "success_soft": "#dfeadb",
    "warning": "#bd8230",
    "warning_soft": "#f4e6c7",
    "danger": "#b44d35",
    "danger_soft": "#f1d5cc",
    "shadow": "rgba(34, 25, 19, 0.08)",
}

FONT_FAMILY = "Noto Sans CJK SC" if IS_RASPBERRY_PI else "Microsoft YaHei"
FONT_STACK = f'"{FONT_FAMILY}", "Droid Sans Fallback", "PingFang SC", "Microsoft YaHei"'


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
    return QFont(FONT_FAMILY, size, weight)


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
    return f"""
    QWidget {{
        font-family: {FONT_STACK};
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
        border-radius: 22px;
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
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 13px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 600;
    }}

    QFrame#mainSurface {{
        background-color: {THEME["bg_alt"]};
        border: 1px solid {THEME["line"]};
        border-radius: 24px;
    }}

    QFrame#footerBar {{
        background-color: {THEME["surface"]};
        border: 1px solid {THEME["line"]};
        border-radius: 18px;
    }}

    QPushButton#navButton {{
        background-color: transparent;
        color: {THEME["muted"]};
        border: none;
        border-radius: 16px;
        padding: 10px 14px;
        font-size: 13px;
        font-weight: 600;
    }}

    QPushButton#navButton:hover {{
        background-color: {THEME["surface_alt"]};
        color: {THEME["ink"]};
    }}

    QPushButton#navButton[active="true"] {{
        background-color: {THEME["header"]};
        color: #fff8ee;
    }}

    QPushButton {{
        border: none;
        border-radius: 16px;
        padding: 10px 14px;
        font-size: 13px;
        font-weight: 600;
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
        background-color: {THEME["surface"]};
        color: {THEME["ink"]};
        border: 1px solid {THEME["line"]};
    }}

    QPushButton#secondaryButton:hover {{
        background-color: #fbf3e7;
    }}

    QPushButton#ghostButton {{
        background-color: transparent;
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
        background-color: #f8efe0;
    }}

    QFrame#accentCard {{
        background-color: {THEME["header"]};
        border: 1px solid {THEME["header_soft"]};
        border-radius: 24px;
    }}

    QLabel#sectionTitle {{
        color: {THEME["ink"]};
        font-size: 18px;
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
        padding: 4px 10px;
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
        font-size: 28px;
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
        background-color: #191513;
        border: 1px solid #43362d;
        border-radius: 26px;
    }}

    QLabel#previewLabel {{
        background-color: #191513;
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
        background-color: {THEME["surface_alt"]};
        border: none;
        border-radius: 8px;
        min-height: 10px;
        max-height: 10px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {THEME["accent"]};
        border-radius: 8px;
    }}

    QMessageBox {{
        background-color: {THEME["surface"]};
    }}
    """
