"""Shared theme helpers for the InkPi 3.5-inch product UI."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication, QLayout

from config import IS_RASPBERRY_PI


THEME = {
    "window": "#F4EEE6",
    "window_deep": "#EFE4D7",
    "surface": "#FFFDF9",
    "surface_alt": "#F4ECE1",
    "surface_soft": "#FAF5EE",
    "ink": "#241A14",
    "ink_soft": "#5C4A3D",
    "muted": "#8D7967",
    "line": "#E4D9CC",
    "line_soft": "#EDE3D7",
    "accent": "#BA0F22",
    "accent_hover": "#9D0C1C",
    "accent_soft": "#F9E7EA",
    "success": "#2B7A59",
    "warning": "#A36A2B",
    "danger": "#B54745",
}

DISPLAY_FONT_FILES = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "SmileySans-Oblique.ttf",
)

DISPLAY_FONT_CANDIDATES = (
    "Smiley Sans",
    "Smiley Sans Oblique",
    "得意黑",
)

BODY_FONT_CANDIDATES = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "Noto Sans SC",
    "PingFang SC",
    "Source Han Sans SC",
    "SimHei",
)

BODY_FONT_FILES = (
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyhbd.ttc",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "simhei.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
)

_DISPLAY_FAMILY: str | None = None
_BODY_FAMILY: str | None = None
_ICON_FAMILY: str | None = None


def _font_families() -> dict[str, str]:
    if QApplication.instance() is None:
        return {}
    return {family.casefold(): family for family in QFontDatabase.families()}


def _register_font_files(files: tuple[Path, ...]) -> list[str]:
    families: list[str] = []
    for font_file in files:
        if not font_file.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id < 0:
            continue
        families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families


def ensure_display_font_family() -> str:
    global _DISPLAY_FAMILY
    if _DISPLAY_FAMILY:
        return _DISPLAY_FAMILY

    families = _font_families()
    for candidate in DISPLAY_FONT_CANDIDATES:
        match = families.get(candidate.casefold())
        if match:
            _DISPLAY_FAMILY = match
            return match

    registered = _register_font_files(DISPLAY_FONT_FILES)
    if registered:
        preferred = registered[0]
        for family in registered:
            if family.casefold() == "smiley sans":
                preferred = family
                break
        _DISPLAY_FAMILY = preferred
        return preferred

    _DISPLAY_FAMILY = ensure_body_font_family()
    return _DISPLAY_FAMILY


def ensure_body_font_family() -> str:
    global _BODY_FAMILY
    if _BODY_FAMILY:
        return _BODY_FAMILY

    families = _font_families()
    for candidate in BODY_FONT_CANDIDATES:
        match = families.get(candidate.casefold())
        if match:
            _BODY_FAMILY = match
            return match

    registered = _register_font_files(BODY_FONT_FILES)
    if registered:
        _BODY_FAMILY = registered[0]
        return registered[0]

    _BODY_FAMILY = "Noto Sans CJK SC" if IS_RASPBERRY_PI else "Microsoft YaHei UI"
    return _BODY_FAMILY


def ensure_app_font_family() -> str:
    return ensure_body_font_family()


def body_font(size: int, weight: int = int(QFont.Weight.Normal)) -> QFont:
    return QFont(ensure_body_font_family(), size, weight)


def display_font(size: int, weight: int = int(QFont.Weight.Bold)) -> QFont:
    return QFont(ensure_display_font_family(), size, weight)


def app_font(size: int, weight: int = int(QFont.Weight.Normal)) -> QFont:
    return body_font(size, weight)


def icon_font(size: int, weight: int = int(QFont.Weight.Normal)) -> QFont:
    global _ICON_FAMILY
    if not _ICON_FAMILY:
        families = _font_families()
        for candidate in (
            "Segoe Fluent Icons",
            "Segoe UI Symbol",
            "Noto Sans Symbols 2",
            ensure_body_font_family(),
        ):
            match = families.get(candidate.casefold())
            if match:
                _ICON_FAMILY = match
                break
        if not _ICON_FAMILY:
            _ICON_FAMILY = ensure_body_font_family()
    return QFont(_ICON_FAMILY, size, weight)


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


def font_stack() -> str:
    ordered = [
        f'"{ensure_body_font_family()}"',
        '"Noto Sans CJK SC"',
        '"Microsoft YaHei UI"',
        '"Microsoft YaHei"',
        '"PingFang SC"',
        "sans-serif",
    ]
    return ", ".join(dict.fromkeys(ordered))


def display_stack() -> str:
    ordered = [
        f'"{ensure_display_font_family()}"',
        f'"{ensure_body_font_family()}"',
        '"Noto Sans CJK SC"',
        '"Microsoft YaHei UI"',
        "sans-serif",
    ]
    return ", ".join(dict.fromkeys(ordered))


def build_stylesheet() -> str:
    body_stack = font_stack()
    heading_stack = display_stack()
    return f"""
    QWidget {{
        background: transparent;
        color: {THEME["ink"]};
        font-family: {body_stack};
        selection-background-color: {THEME["accent"]};
        selection-color: #ffffff;
    }}

    QMainWindow {{
        background: qlineargradient(
            x1: 0,
            y1: 0,
            x2: 1,
            y2: 1,
            stop: 0 {THEME["window"]},
            stop: 1 {THEME["window_deep"]}
        );
    }}

    QFrame#mainSurface,
    QFrame#pageHeader {{
        border: none;
        background: transparent;
    }}

    QFrame#scoreCard,
    QFrame#metricPanel,
    QFrame#historyItemCard,
    QFrame#historyGlyphCard,
    QFrame#softCard,
    QFrame#heroCard,
    QFrame#actionCard,
    QFrame#resultSummaryCard,
    QFrame#feedbackCard,
    QLabel#previewLabel {{
        background-color: {THEME["surface"]};
        border: 1px solid {THEME["line"]};
        border-radius: 28px;
    }}

    QFrame#metricPanel,
    QFrame#historyGlyphCard,
    QFrame#softCard,
    QFrame#actionCard {{
        background-color: {THEME["surface_alt"]};
        border-color: {THEME["line_soft"]};
    }}

    QFrame#bottomNav {{
        background: rgba(255, 252, 247, 0.88);
        border-top: 1px solid {THEME["line"]};
    }}

    QLabel#brandTitle,
    QLabel#brandAccent,
    QLabel#headlineTitle,
    QLabel#pageTitle,
    QLabel#sectionTitle,
    QLabel#scoreNumber,
    QLabel#scoreGrade,
    QPushButton#primaryButton,
    QPushButton#secondaryButton,
    QPushButton#floatingButton,
    QPushButton#navButton {{
        font-family: {heading_stack};
    }}

    QLabel#brandTitle {{
        color: {THEME["ink"]};
        font-size: 22px;
        font-weight: 700;
    }}

    QLabel#brandAccent {{
        color: {THEME["accent"]};
        font-size: 34px;
        font-weight: 800;
    }}

    QLabel#pageTitle {{
        color: {THEME["muted"]};
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
    }}

    QLabel#headlineTitle {{
        color: {THEME["ink"]};
        font-size: 21px;
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
        font-size: 56px;
        font-weight: 900;
    }}

    QLabel#scoreGrade {{
        color: #ffffff;
        background-color: {THEME["accent"]};
        border-radius: 18px;
        padding: 5px 12px;
        font-size: 18px;
        font-weight: 800;
    }}

    QLabel#historyScore {{
        color: {THEME["ink"]};
        font-size: 26px;
        font-weight: 800;
    }}

    QLabel#historyGrade {{
        color: {THEME["accent"]};
        font-size: 16px;
        font-weight: 900;
    }}

    QLabel#glyphLabel {{
        color: {THEME["ink"]};
        font-size: 24px;
        font-weight: 900;
        font-family: {heading_stack};
    }}

    QLabel#statusPill {{
        background-color: {THEME["surface_alt"]};
        color: {THEME["muted"]};
        border-radius: 13px;
        padding: 5px 10px;
        font-size: 10px;
        font-weight: 700;
    }}

    QLabel#statusPill[state="ready"] {{
        background-color: #E6F1EA;
        color: {THEME["success"]};
    }}

    QLabel#statusPill[state="working"] {{
        background-color: #F6E8D7;
        color: {THEME["warning"]};
    }}

    QLabel#statusPill[state="error"] {{
        background-color: #F5E0DF;
        color: {THEME["danger"]};
    }}

    QPushButton {{
        background-color: {THEME["surface_alt"]};
        color: {THEME["ink"]};
        border: none;
        border-radius: 22px;
        padding: 10px 16px;
        font-size: 12px;
        font-weight: 700;
    }}

    QPushButton:hover {{
        background-color: #EDE2D6;
    }}

    QPushButton:pressed {{
        background-color: #E3D7CA;
    }}

    QPushButton:disabled {{
        background-color: #F1EBE3;
        color: #B4A89B;
    }}

    QPushButton#primaryButton {{
        background-color: {THEME["accent"]};
        color: #ffffff;
        border-radius: 26px;
        padding-left: 20px;
        padding-right: 20px;
    }}

    QPushButton#primaryButton:hover {{
        background-color: {THEME["accent_hover"]};
    }}

    QPushButton#secondaryButton,
    QPushButton#ghostButton,
    QPushButton#buttonCard {{
        background-color: {THEME["surface"]};
        color: {THEME["ink"]};
        border: 1px solid {THEME["line_soft"]};
        border-radius: 24px;
    }}

    QPushButton#floatingButton {{
        background-color: {THEME["accent"]};
        color: #ffffff;
        border-radius: 28px;
        font-size: 22px;
        font-weight: 900;
    }}

    QPushButton#headerIconButton {{
        background-color: {THEME["surface"]};
        color: {THEME["ink_soft"]};
        border: 1px solid {THEME["line_soft"]};
        border-radius: 14px;
        font-size: 14px;
        font-weight: 700;
        padding: 0;
    }}

    QPushButton#navButton {{
        background: transparent;
        color: {THEME["muted"]};
        border-radius: 12px;
        padding: 4px 0;
        font-size: 10px;
        font-weight: 800;
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
        background: #D6CABC;
        border-radius: 3px;
        min-height: 18px;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        border: none;
        background: transparent;
        height: 0;
    }}

    QProgressBar {{
        background-color: #EAE2D9;
        border: none;
        border-radius: 5px;
        min-height: 10px;
        max-height: 10px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {THEME["accent"]};
        border-radius: 5px;
    }}

    QLabel#previewLabel {{
        background-color: {THEME["surface_soft"]};
        color: {THEME["muted"]};
        border-radius: 26px;
        padding: 4px;
    }}

    QMessageBox {{
        background-color: {THEME["surface"]};
    }}
    """
