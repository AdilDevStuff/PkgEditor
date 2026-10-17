"""
Vector Icon Manager for PkgEditor.
Generates crisp, high-DPI QIcon and QPixmap objects from embedded SVGs.
Eliminates missing emoji boxes on Linux, Windows, and macOS.
"""
from .qt_compat import QtGui, QtCore, QtWidgets

try:
    from PyQt5 import QtSvg
except ImportError:
    try:
        from PyQt6 import QtSvg
    except ImportError:
        try:
            from PySide6 import QtSvg
        except ImportError:
            QtSvg = None


SVG_DEFS = {
    "folder-open": """<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path><path d="M2 10h20"></path>""",
    "folder": """<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>""",
    "file": """<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline>""",
    "file-text": """<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><line x1="10" y1="9" x2="8" y2="9"></line>""",
    "package": """<line x1="16.5" y1="9.4" x2="7.55" y2="4.21"></line><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line>""",
    "merge": """<circle cx="18" cy="18" r="3"></circle><circle cx="6" cy="6" r="3"></circle><path d="M6 21V9a9 9 0 0 0 9 9"></path>""",
    "key": """<path d="M21 2l-2 2m-1.5 1.5L14 9l-3 3-2-2-4 4 3 3-2 2 3 3 4-4-2-2 3-3 3.5-3.5"></path><circle cx="17.5" cy="6.5" r="2.5"></circle>""",
    "lock": """<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path>""",
    "unlock": """<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 9.9-1"></path>""",
    "extract": """<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line>""",
    "download": """<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line>""",
    "theme": """<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>""",
    "plus": """<line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line>""",
    "edit": """<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>""",
    "delete": """<polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>""",
    "check": """<polyline points="20 6 9 17 4 12"></polyline>""",
    "save": """<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline>""",
    "settings": """<circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>""",
    "table": """<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="3" y1="15" x2="21" y2="15"></line><line x1="9" y1="3" x2="9" y2="21"></line><line x1="15" y1="3" x2="15" y2="21"></line>""",
    "shield": """<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>""",
    "calculator": """<rect x="4" y="2" width="16" height="20" rx="2"></rect><line x1="8" y1="6" x2="16" y2="6"></line><line x1="16" y1="14" x2="16" y2="18"></line><path d="M16 10h.01"></path><path d="M12 10h.01"></path><path d="M8 10h.01"></path><path d="M12 14h.01"></path><path d="M8 14h.01"></path><path d="M12 18h.01"></path><path d="M8 18h.01"></path>""",
    "info": """<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>""",
}


def _render_svg(svg_inner: str, color: str, size: int) -> QtGui.QPixmap:
    xml = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'{svg_inner}'
        f'</svg>'
    )
    pix = QtGui.QPixmap(size, size)
    pix.fill(QtCore.Qt.GlobalColor.transparent if hasattr(QtCore.Qt, "GlobalColor") else QtCore.Qt.transparent)

    if QtSvg:
        renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(xml.encode("utf-8")))
        painter = QtGui.QPainter(pix)
        renderer.render(painter)
        painter.end()

    return pix


_icon_cache = {}


def get_pixmap(name: str, color: str = "#0084ff", size: int = 48) -> QtGui.QPixmap:
    key = (name, color, size)
    if key in _icon_cache:
        return _icon_cache[key]

    inner = SVG_DEFS.get(name, SVG_DEFS["file"])
    pix = _render_svg(inner, color, size)
    _icon_cache[key] = pix
    return pix


def get_icon(name: str, normal_color: str = "#e0e0e0", active_color: str = "#0084ff", disabled_color: str = "#5d6175", size: int = 24) -> QtGui.QIcon:
    cache_key = (name, normal_color, active_color, disabled_color, size, "icon")
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    inner = SVG_DEFS.get(name, SVG_DEFS["file"])
    icon = QtGui.QIcon()

    normal_pix = _render_svg(inner, normal_color, size)
    active_pix = _render_svg(inner, active_color, size)
    disabled_pix = _render_svg(inner, disabled_color, size)

    # Add states
    icon.addPixmap(normal_pix, QtGui.QIcon.Mode.Normal if hasattr(QtGui.QIcon, "Mode") else QtGui.QIcon.Normal)
    icon.addPixmap(active_pix, QtGui.QIcon.Mode.Active if hasattr(QtGui.QIcon, "Mode") else QtGui.QIcon.Active)
    icon.addPixmap(active_pix, QtGui.QIcon.Mode.Selected if hasattr(QtGui.QIcon, "Mode") else QtGui.QIcon.Selected)
    icon.addPixmap(disabled_pix, QtGui.QIcon.Mode.Disabled if hasattr(QtGui.QIcon, "Mode") else QtGui.QIcon.Disabled)

    _icon_cache[cache_key] = icon
    return icon
