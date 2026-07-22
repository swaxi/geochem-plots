"""
Geochemistry Plotting Tools - Dock Widget
==========================================
Contains the main dockable widget with all plotting functionality.
"""

import os
import json
import random
from collections import Counter
import matplotlib.colors as mcolors
from qgis.core import QgsProject, QgsVectorLayer, QgsField, NULL
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QListWidget, QListWidgetItem, QCheckBox,
    QFileDialog, QMessageBox, QGroupBox, QTabWidget,
    QGridLayout, QRadioButton, QButtonGroup, QScrollArea,
    QDialog, QFormLayout, QDoubleSpinBox, QColorDialog, QInputDialog,
    QDialogButtonBox, QSizePolicy
)
from qgis.PyQt.QtGui import QColor, QPainter, QPen, QBrush, QPolygonF
from qgis.PyQt.QtCore import Qt, QVariant, pyqtSignal, QPointF, QRectF, QSize

try:
    import matplotlib
    try:
        from qgis.PyQt.QtCore import QT_VERSION_STR
        qt_major = int(QT_VERSION_STR.split('.')[0])
        
        if qt_major >= 6:
            matplotlib.use('QtAgg')  # Unified backend for Qt6+
        else:
            matplotlib.use('Qt5Agg')
    except Exception:
        matplotlib.use('Qt5Agg')  # Fallback    
    
    import matplotlib.pyplot as plt

    import matplotlib.ticker as ticker
    from matplotlib.patches import Polygon
    from matplotlib.lines import Line2D
    from matplotlib.widgets import RectangleSelector, CheckButtons, Button
    from matplotlib.path import Path
    from matplotlib.markers import MarkerStyle
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Qt5/Qt6 Compatibility Layer
try:
    # Try Qt6 style first
    _test = Qt.DockWidgetArea.RightDockWidgetArea
    # Qt6 detected
    QT6 = True

    # Qt6 style enums are already available
    RightDockWidgetArea = Qt.DockWidgetArea.RightDockWidgetArea
    LeftDockWidgetArea = Qt.DockWidgetArea.LeftDockWidgetArea
    TopDockWidgetArea = Qt.DockWidgetArea.TopDockWidgetArea
    BottomDockWidgetArea = Qt.DockWidgetArea.BottomDockWidgetArea

    # QMessageBox buttons
    QMessageBox_Ok = QMessageBox.StandardButton.Ok
    QMessageBox_Cancel = QMessageBox.StandardButton.Cancel
    QMessageBox_Yes = QMessageBox.StandardButton.Yes
    QMessageBox_No = QMessageBox.StandardButton.No

    QListWidget_MultiSelection = QListWidget.SelectionMode.MultiSelection
    Qt_ScrollBarAlwaysOff = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    Qt_ScrollBarAsNeeded = Qt.ScrollBarPolicy.ScrollBarAsNeeded
    Qt_UserRole = Qt.ItemDataRole.UserRole

    # Category style panel (interactive legend) enums
    Qt_NoBrush = Qt.BrushStyle.NoBrush
    QDialog_Accepted = QDialog.DialogCode.Accepted
    QDialogButtonBox_Ok = QDialogButtonBox.StandardButton.Ok
    QDialogButtonBox_Cancel = QDialogButtonBox.StandardButton.Cancel
    QSizePolicy_Fixed = QSizePolicy.Policy.Fixed
    QSizePolicy_Preferred = QSizePolicy.Policy.Preferred
    QSizePolicy_Ignored = QSizePolicy.Policy.Ignored
    QSizePolicy_Minimum = QSizePolicy.Policy.Minimum
    QSizePolicy_Expanding = QSizePolicy.Policy.Expanding
    QDockWidget_Movable = QDockWidget.DockWidgetFeature.DockWidgetMovable
    QDockWidget_Floatable = QDockWidget.DockWidgetFeature.DockWidgetFloatable

except AttributeError:
    # Qt5 detected
    QT6 = False

    # Qt5 style enums
    RightDockWidgetArea = Qt.RightDockWidgetArea
    LeftDockWidgetArea = Qt.LeftDockWidgetArea
    TopDockWidgetArea = Qt.TopDockWidgetArea
    BottomDockWidgetArea = Qt.BottomDockWidgetArea

    # QMessageBox buttons
    QMessageBox_Ok = QMessageBox.Ok
    QMessageBox_Cancel = QMessageBox.Cancel
    QMessageBox_Yes = QMessageBox.Yes
    QMessageBox_No = QMessageBox.No

    QListWidget_MultiSelection = QListWidget.MultiSelection
    Qt_ScrollBarAlwaysOff = Qt.ScrollBarAlwaysOff
    Qt_ScrollBarAsNeeded = Qt.ScrollBarAsNeeded
    Qt_UserRole = Qt.UserRole

    # Category style panel (interactive legend) enums
    Qt_NoBrush = Qt.NoBrush
    QDialog_Accepted = QDialog.Accepted
    QDialogButtonBox_Ok = QDialogButtonBox.Ok
    QDialogButtonBox_Cancel = QDialogButtonBox.Cancel
    QSizePolicy_Fixed = QSizePolicy.Fixed
    QSizePolicy_Preferred = QSizePolicy.Preferred
    QSizePolicy_Ignored = QSizePolicy.Ignored
    QSizePolicy_Minimum = QSizePolicy.Minimum
    QSizePolicy_Expanding = QSizePolicy.Expanding
    QDockWidget_Movable = QDockWidget.DockWidgetMovable
    QDockWidget_Floatable = QDockWidget.DockWidgetFloatable


# =============================================================================
# CATEGORICAL COLOUR MAPPING UTILITIES
# =============================================================================

CATEGORY_MARKERS = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*', 'P', 'X', 'd', '8', 'H']

# Sentinel shown as the first entry of the "Category:" field combo, letting
# users opt out of per-category colouring/markers entirely and plot every
# selected sample with a single shared symbol.
NO_CATEGORY_OPTION = "(none) — plot all points with one symbol"
NO_CATEGORY_LABEL = "All points"

# Marker shapes offered by the interactive category style dialog, paired with
# a human-readable label. Restricted to the subset that _MarkerSymbolWidget
# knows how to draw as a crisp vector glyph.
STYLE_MARKER_OPTIONS = [
    ('Circle', 'o'), ('Square', 's'), ('Triangle up', '^'),
    ('Triangle down', 'v'), ('Diamond', 'D'), ('Plus', 'P'),
    ('Cross', 'X'), ('Star', '*'), ('Triangle left', '<'),
    ('Triangle right', '>'),
]


class _MarkerSymbolWidget(QWidget):
    """Vector marker preview used by the interactive category legend.

    Painted directly with QPainter (rather than a raster pixmap) so it stays
    crisp at any size and can be restyled live via set_symbol_style().
    """

    def __init__(self, marker, colour, parent=None):
        super().__init__(parent)
        self.marker = marker or 'o'
        try:
            qcolour = QColor(mcolors.to_hex(mcolors.to_rgba(colour or '#000000')))
        except Exception:
            qcolour = QColor('#000000')
        self.colour = qcolour
        self.setMinimumSize(24, 24)
        self.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)

    def sizeHint(self):
        return QSize(24, 24)

    def set_symbol_style(self, marker, colour):
        self.marker = marker or 'o'
        try:
            self.colour = QColor(mcolors.to_hex(mcolors.to_rgba(colour or '#000000')))
        except Exception:
            self.colour = QColor('#000000')
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        side = min(self.width(), self.height())
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        r = side * 0.30

        pen = QPen(self.colour)
        pen.setWidthF(max(1.2, side * 0.09))
        painter.setPen(pen)
        painter.setBrush(QBrush(self.colour))

        m = self.marker
        if m == 'o':
            painter.drawEllipse(QPointF(cx, cy), r, r)
        elif m == 's':
            painter.drawRect(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        elif m == '^':
            painter.drawPolygon(QPolygonF([
                QPointF(cx, cy - r), QPointF(cx - r, cy + r), QPointF(cx + r, cy + r)]))
        elif m == 'v':
            painter.drawPolygon(QPolygonF([
                QPointF(cx - r, cy - r), QPointF(cx + r, cy - r), QPointF(cx, cy + r)]))
        elif m == '<':
            painter.drawPolygon(QPolygonF([
                QPointF(cx - r, cy), QPointF(cx + r, cy - r), QPointF(cx + r, cy + r)]))
        elif m == '>':
            painter.drawPolygon(QPolygonF([
                QPointF(cx + r, cy), QPointF(cx - r, cy - r), QPointF(cx - r, cy + r)]))
        elif m == 'D':
            painter.drawPolygon(QPolygonF([
                QPointF(cx, cy - r), QPointF(cx + r, cy), QPointF(cx, cy + r), QPointF(cx - r, cy)]))
        elif m in ('P', '+'):
            painter.setBrush(Qt_NoBrush)
            painter.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
            painter.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
            if m == 'P':
                painter.setBrush(QBrush(self.colour))
                painter.drawRect(QRectF(cx - r * 0.38, cy - r * 0.38, r * 0.76, r * 0.76))
        elif m in ('X', 'x'):
            painter.setBrush(Qt_NoBrush)
            painter.drawLine(QPointF(cx - r, cy - r), QPointF(cx + r, cy + r))
            painter.drawLine(QPointF(cx - r, cy + r), QPointF(cx + r, cy - r))
        elif m == '*':
            painter.setBrush(Qt_NoBrush)
            painter.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
            painter.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
            painter.drawLine(QPointF(cx - r * 0.72, cy - r * 0.72), QPointF(cx + r * 0.72, cy + r * 0.72))
            painter.drawLine(QPointF(cx - r * 0.72, cy + r * 0.72), QPointF(cx + r * 0.72, cy - r * 0.72))
        else:
            painter.drawEllipse(QPointF(cx, cy), r, r)

        painter.end()


def create_categorical_color_map(sample_names):
    """Create a colour and marker map based on unique category values in sample_names."""
    unique_categories = list(dict.fromkeys(sample_names))
    n_categories = len(unique_categories)
    
    if n_categories <= 10:
        cmap = plt.cm.tab10
        colors = [cmap(i / 10) for i in range(n_categories)]
    elif n_categories <= 20:
        cmap = plt.cm.tab20
        colors = [cmap(i / 20) for i in range(n_categories)]
    else:
        cmap = plt.cm.turbo
        colors = [cmap(i / n_categories) for i in range(n_categories)]
    
    category_colors = {cat: colors[i] for i, cat in enumerate(unique_categories)}
    category_markers = {cat: CATEGORY_MARKERS[i % len(CATEGORY_MARKERS)] for i, cat in enumerate(unique_categories)}
    
    sample_colors = [category_colors[name] for name in sample_names]
    sample_markers = [category_markers[name] for name in sample_names]
    
    return category_colors, sample_colors, unique_categories, category_markers, sample_markers


# =============================================================================
# NORMALIZATION VALUES
# =============================================================================

# Chondrite normalisation values

SUN_MCDONOUGH_1989_C1_CHONDRITE_VALUES = {
    'Li': 1.57, 'F': 60.7, 'P': 1220.0, 'K': 545.0,
    'Ti': 445.0, 'Rb': 2.32, 'Sr': 7.26, 'Y': 1.57,
    'Zr': 3.87, 'Nb': 0.246, 'Mo': 0.92, 'Sn': 1.72,
    'Sb': 0.16, 'Cs': 0.188, 'Ba': 2.41, 'La': 0.237,
    'Ce': 0.612, 'Pr': 0.095, 'Nd': 0.467, 'Sm': 0.153,
    'Eu': 0.058, 'Gd': 0.2055, 'Tb': 0.0374, 'Dy': 0.254,
    'Ho': 0.0566, 'Er': 0.1655, 'Tm': 0.0255, 'Yb': 0.17,
    'Lu': 0.0254, 'Hf': 0.1066, 'Ta': 0.014, 'W': 0.095,
    'Tl': 0.14, 'Pb': 2.47, 'Th': 0.029, 'U': 0.008,
}
MCDONOUGH_SUN_1995_C1_CHONDRITE_VALUES = {
    'Li': 1.5, 'Be': 0.025, 'B': 0.9, 'C': 35000.0,
    'N': 3180.0, 'F': 60.0, 'Na': 5100.0, 'Mg': 96500.0,
    'Al': 8600.0, 'Si': 106500.0, 'P': 1080.0, 'S': 54000.0,
    'Cl': 680.0, 'K': 550.0, 'Ca': 9250.0, 'Sc': 5.92,
    'Ti': 440.0, 'V': 56.0, 'Cr': 2650.0, 'Mn': 1920.0,
    'Fe': 181000.0, 'Co': 500.0, 'Ni': 10500.0, 'Cu': 120.0,
    'Zn': 310.0, 'Ga': 9.2, 'Ge': 31.0, 'As': 1.85,
    'Se': 21.0, 'Br': 3.57, 'Rb': 2.3, 'Sr': 7.25,
    'Y': 1.57, 'Zr': 3.82, 'Nb': 0.24, 'Mo': 0.9,
    'Ru': 0.71, 'Rh': 0.13, 'Pd': 0.55, 'Ag': 0.2,
    'Cd': 0.71, 'In': 0.08, 'Sn': 1.65, 'Sb': 0.14,
    'Te': 2.33, 'I': 0.45, 'Cs': 0.19, 'Ba': 2.41,
    'La': 0.237, 'Ce': 0.613, 'Pr': 0.0928, 'Nd': 0.457,
    'Sm': 0.148, 'Eu': 0.056299999999999996, 'Gd': 0.199, 'Tb': 0.0361,
    'Dy': 0.246, 'Ho': 0.0546, 'Er': 0.16, 'Tm': 0.0247,
    'Yb': 0.161, 'Lu': 0.0246, 'Hf': 0.103, 'Ta': 0.0136,
    'W': 0.093, 'Re': 0.04, 'Os': 0.49, 'Ir': 0.455,
    'Pt': 1.01, 'Au': 0.14, 'Hg': 0.3, 'Tl': 0.14,
    'Pb': 2.47, 'Bi': 0.11, 'Th': 0.029, 'U': 0.0074,
}
BOYNTON_1984_CHONDRITE_VALUES = {
    'La': 0.31, 'Ce': 0.808, 'Pr': 0.122, 'Nd': 0.6,
    'Sm': 0.195, 'Eu': 0.0735, 'Gd': 0.259, 'Tb': 0.0474,
    'Dy': 0.322, 'Ho': 0.0718, 'Er': 0.21, 'Tm': 0.0324,
    'Yb': 0.209, 'Lu': 0.0322,
}
NAKAMURA_1974_CHONDRITE_VALUES = {
    'La': 0.329, 'Ce': 0.865, 'Pr': 0.112, 'Nd': 0.63,
    'Sm': 0.203, 'Eu': 0.077, 'Gd': 0.276, 'Tb': 0.047,
    'Dy': 0.343, 'Ho': 0.07, 'Er': 0.225, 'Tm': 0.03,
    'Yb': 0.22, 'Lu': 0.0339,
}

# Backwards-compatible alias used by existing code paths.
CHONDRITE_VALUES = MCDONOUGH_SUN_1995_C1_CHONDRITE_VALUES

# Primitive mantle, depleted mantle and other normalisation values

PRIMITIVE_MANTLE_MCDONOUGH_SUN_1995_VALUES = {
    'Ag': 0.008, 'Al': 23500, 'As': 0.05, 'Au': 0.001, 'B': 0.3, 'Ba': 6.6, 'Be': 0.068,
    'Bi': 0.0025, 'Br': 0.05, 'C': 120, 'Ca': 25300, 'Cd': 0.04, 'Ce': 1.675, 'Cl': 17,
    'Co': 105, 'Cr': 2625, 'Cs': 0.021, 'Cu': 30, 'Dy': 0.674, 'Er': 0.438, 'Eu': 0.154,
    'F': 25, 'Fe': 62600, 'Ga': 4, 'Gd': 0.544, 'Ge': 1.1, 'Hf': 0.283, 'Hg': 0.01,
    'Ho': 0.149, 'I': 0.01, 'In': 0.011, 'Ir': 0.0032, 'K': 240, 'La': 0.648, 'Li': 1.6,
    'Lu': 0.0675, 'Mg': 228000, 'Mn': 1045, 'Mo': 0.05, 'N': 2, 'Na': 2670, 'Nb': 0.658,
    'Nd': 1.25, 'Ni': 1960, 'Os': 0.0034, 'P': 90, 'Pb': 0.15, 'Pd': 0.0039, 'Pr': 0.254,
    'Pt': 0.0071, 'Rb': 0.6, 'Re': 0.00028, 'Rh': 0.0009, 'Ru': 0.005, 'S': 250, 'Sb': 0.0055,
    'Sc': 16.2, 'Se': 0.075, 'Si': 210000, 'Sm': 0.406, 'Sn': 0.13, 'Sr': 19.9, 'Ta': 0.037,
    'Tb': 0.099, 'Te': 0.012, 'Th': 0.0795, 'Ti': 1205, 'Tl': 0.0035, 'Tm': 0.068,
    'U': 0.0203, 'V': 82, 'W': 0.029, 'Y': 4.3, 'Yb': 0.441, 'Zn': 55, 'Zr': 10.5,
}

DEPLETED_MANTLE_SALTERS_STRACKE_2004_VALUES = {
    'Ag': 0.006, 'Ar': 0.00121, 'As': 0.0074, 'Au': 0.001, 'Be': 0.025, 'Bi': 0.00039,
    'Cs': 0.00132, 'He': 0.000157, 'Hg': 0.01, 'In': 0.0122, 'Ir': 0.0029, 'La': 0.234,
    'Li': 0.7, 'Lu': 0.063, 'Mo': 0.025, 'N': 0.04, 'Nb': 0.21, 'Nd': 0.713, 'Ni': 1960,
    'Os': 0.00299, 'P': 40.7, 'Pb': 0.0232, 'Pd': 0.0052, 'Pr': 0.131, 'Pt': 0.0062,
    'Rb': 0.088, 'Re': 0.000157, 'Rh': 0.001, 'Ru': 0.0057, 'S': 119, 'Sb': 0.0026,
    'Sc': 16.3, 'Se': 0.072, 'Sm': 0.27, 'Sn': 0.1, 'Sr': 9.8, 'Ta': 0.0138, 'Tb': 0.075,
    'Te': 0.0151, 'Th': 0.0137, 'Ti': 798, 'Tl': 0.00038, 'Tm': 0.06, 'U': 0.0047, 'V': 79,
    'W': 0.0035, 'Y': 4.07, 'Yb': 0.401, 'Zn': 56, 'Zr': 7.94,
}

DEPLETED_MANTLE_WORKMAN_HART_2005_VALUES = {
    'Gd': 0.358, 'Hf': 0.157, 'Ho': 0.115, 'La': 0.192, 'Lu': 0.058, 'Nb': 0.1485,
    'Nd': 0.581, 'Pb': 0.018, 'Pr': 0.107, 'Rb': 0.05, 'Sm': 0.239, 'Sr': 7.664, 'Ta': 0.0096,
    'Tb': 0.07, 'Th': 0.0079, 'Ti': 716.3, 'U': 0.0032, 'Y': 3.328, 'Yb': 0.365, 'Zr': 5.082,
}

PRIMITIVE_MANTLE_SUN_MCDONOUGH_1989_VALUES = {
    'Cs': 0.032, 'Tl': 0.005, 'Rb': 0.635, 'Ba': 6.989, 'W': 0.020,
    'Th': 0.085, 'U': 0.021, 'Nb': 0.713, 'Ta': 0.041, 'K': 250,
    'La': 0.687, 'Ce': 1.775, 'Pb': 0.185, 'Pr': 0.276, 'Mo': 0.063,
    'Sr': 21.1, 'P': 95, 'Nd': 1.354, 'F': 26, 'Sm': 0.444,
    'Zr': 11.2, 'Hf': 0.309, 'Eu': 0.168, 'Sn': 0.170, 'Sb': 0.005,
    'Ti': 1300, 'Gd': 0.596, 'Tb': 0.108, 'Dy': 0.737, 'Li': 1.60,
    'Y': 4.55, 'Ho': 0.164, 'Er': 0.480, 'Tm': 0.074, 'Yb': 0.493,
    'Lu': 0.074,
}

N_TYPE_MORB_SUN_MCDONOUGH_1989_VALUES = {
    'Cs': 0.0070, 'Tl': 0.0014, 'Rb': 0.56, 'Ba': 6.30, 'W': 0.010,
    'Th': 0.120, 'U': 0.047, 'Nb': 2.33, 'Ta': 0.132, 'K': 600,
    'La': 2.50, 'Ce': 7.50, 'Pb': 0.30, 'Pr': 1.32, 'Mo': 0.31,
    'Sr': 90, 'P': 510, 'Nd': 7.30, 'F': 210, 'Sm': 2.63,
    'Zr': 74, 'Hf': 2.05, 'Eu': 1.02, 'Sn': 1.1, 'Sb': 0.01,
    'Ti': 7600, 'Gd': 3.680, 'Tb': 0.670, 'Dy': 4.550, 'Li': 4.3,
    'Y': 28, 'Ho': 1.01, 'Er': 2.97, 'Tm': 0.456, 'Yb': 3.05,
    'Lu': 0.455,
}

E_TYPE_MORB_SUN_MCDONOUGH_1989_VALUES = {
    'Cs': 0.063, 'Tl': 0.013, 'Rb': 5.04, 'Ba': 57, 'W': 0.092,
    'Th': 0.60, 'U': 0.18, 'Nb': 8.30, 'Ta': 0.47, 'K': 2100,
    'La': 6.30, 'Ce': 15.0, 'Pb': 0.60, 'Pr': 2.05, 'Mo': 0.47,
    'Sr': 155, 'P': 620, 'Nd': 9.00, 'F': 250, 'Sm': 2.60,
    'Zr': 73, 'Hf': 2.03, 'Eu': 0.91, 'Sn': 0.8, 'Sb': 0.01,
    'Ti': 6000, 'Gd': 2.970, 'Tb': 0.530, 'Dy': 3.550, 'Li': 3.5,
    'Y': 22, 'Ho': 0.790, 'Er': 2.31, 'Tm': 0.356, 'Yb': 2.37,
    'Lu': 0.354,
}

OIB_SUN_MCDONOUGH_1989_VALUES = {
    'Cs': 0.387, 'Tl': 0.077, 'Rb': 31.0, 'Ba': 350, 'W': 0.560,
    'Th': 4.00, 'U': 1.02, 'Nb': 48.0, 'Ta': 2.70, 'K': 12000,
    'La': 37.0, 'Ce': 80.0, 'Pb': 3.20, 'Pr': 9.70, 'Mo': 2.40,
    'Sr': 660, 'P': 2700, 'Nd': 38.5, 'F': 1150, 'Sm': 10.0,
    'Zr': 280, 'Hf': 7.80, 'Eu': 3.00, 'Sn': 2.7, 'Sb': 0.03,
    'Ti': 17200, 'Gd': 7.620, 'Tb': 1.050, 'Dy': 5.600, 'Li': 5.6,
    'Y': 29, 'Ho': 1.06, 'Er': 2.62, 'Tm': 0.350, 'Yb': 2.16,
    'Lu': 0.300,
}

# Upper continental crust normalisation values. Major-element entries are
# converted to ppm-equivalent elemental concentrations where required by the
# existing spider-diagram routines (K from K2O, Ti from TiO2, P from P2O5).

UPPER_CONTINENTAL_CRUST_RUDNICK_GAO_2003_VALUES = {
    'Li': 24, 'Be': 2.1, 'B': 17, 'N': 83, 'F': 557, 'S': 621, 'Cl': 370,
    'K': 23243, 'Sc': 14.0, 'Ti': 3837, 'V': 97, 'Cr': 92, 'Co': 17.3,
    'Ni': 47, 'Cu': 28, 'Zn': 67, 'Ga': 17.5, 'Ge': 1.4, 'As': 4.8,
    'Se': 0.09, 'Br': 1.6, 'Rb': 84, 'Sr': 320, 'Y': 21, 'Zr': 193,
    'Nb': 12, 'Mo': 1.1, 'Ag': 0.053, 'Cd': 0.09, 'In': 0.056,
    'Sn': 2.1, 'Sb': 0.4, 'I': 1.4, 'Cs': 4.9, 'Ba': 624,
    'La': 31, 'Ce': 63, 'Pr': 7.1, 'Nd': 27, 'Sm': 4.7, 'Eu': 1.0,
    'Gd': 4.0, 'Tb': 0.7, 'Dy': 3.9, 'Ho': 0.83, 'Er': 2.3,
    'Tm': 0.30, 'Yb': 2.0, 'Lu': 0.31, 'Hf': 5.3, 'Ta': 0.9,
    'W': 1.9, 'Re': 0.000198, 'Os': 0.000031, 'Ir': 0.000022,
    'Pt': 0.0005, 'Au': 0.0015, 'Hg': 0.05, 'Tl': 0.9, 'Pb': 17,
    'Bi': 0.16, 'Th': 10.5, 'U': 2.7, 'P': 655,
}

UPPER_CONTINENTAL_CRUST_TAYLOR_MCLENNAN_1985_VALUES = {
    'K': 28141, 'Ti': 2998, 'P': 873, 'Rb': 112, 'Sr': 350, 'Y': 22,
    'Zr': 190, 'Ba': 550, 'La': 30, 'Ce': 64, 'Nd': 26, 'Sm': 4.5,
    'Eu': 0.88, 'Tb': 0.64, 'Yb': 2.2, 'Lu': 0.32, 'Hf': 5.8,
    'Ta': 1.5, 'Pb': 17, 'Th': 10.7, 'U': 2.8,
}

# Backwards-compatible alias used by existing code paths.
PRIMITIVE_MANTLE_VALUES = PRIMITIVE_MANTLE_MCDONOUGH_SUN_1995_VALUES

NORMALIZATION_OPTIONS = [
    ("Chondrite - Sun and McDonough (1989) (C1 chondrite)", SUN_MCDONOUGH_1989_C1_CHONDRITE_VALUES),
    ("Chondrite - McDonough and Sun (1995) (C1 chondrite)", MCDONOUGH_SUN_1995_C1_CHONDRITE_VALUES),
    ("Chondrite - Boynton (1984)", BOYNTON_1984_CHONDRITE_VALUES),
    ("Chondrite - Nakamura (1974)", NAKAMURA_1974_CHONDRITE_VALUES),
    ("Primitive Mantle - Sun and McDonough (1989)", PRIMITIVE_MANTLE_SUN_MCDONOUGH_1989_VALUES),
    ("Primitive Mantle - McDonough and Sun (1995)", PRIMITIVE_MANTLE_MCDONOUGH_SUN_1995_VALUES),
    ("OIB - Sun and McDonough (1989)", OIB_SUN_MCDONOUGH_1989_VALUES),
    ("N-MORB - Sun and McDonough (1989)", N_TYPE_MORB_SUN_MCDONOUGH_1989_VALUES),
    ("E-MORB - Sun and McDonough (1989)", E_TYPE_MORB_SUN_MCDONOUGH_1989_VALUES),
    ("Depleted Mantle - Salters and Stracke (2004)", DEPLETED_MANTLE_SALTERS_STRACKE_2004_VALUES),
    ("Depleted Mantle - Workman and Hart (2005)", DEPLETED_MANTLE_WORKMAN_HART_2005_VALUES),
    ("Upper Continental Crust - Rudnick and Gao (2003)", UPPER_CONTINENTAL_CRUST_RUDNICK_GAO_2003_VALUES),
    ("Upper Continental Crust - Taylor and McLennan (1985)", UPPER_CONTINENTAL_CRUST_TAYLOR_MCLENNAN_1985_VALUES),
]

EXTENDED_SPIDER_ORDER = [
    'Ba', 'Rb', 'Th', 'K', 'Nb', 'Ta', 'La', 'Ce', 'Sr', 'Nd',
    'P', 'Sm', 'Zr', 'Hf', 'Ti', 'Tb', 'Y', 'Tm', 'Yb'
]

REE_ORDER = [
    'La', 'Ce', 'Pr', 'Nd', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu'
]

EXTENDED_ORDER_ALT = [
    'Cs', 'Rb', 'Ba', 'Th', 'U', 'Nb', 'Ta', 'K', 'La', 'Ce', 'Pb',
    'Pr', 'Sr', 'Nd', 'Sm', 'Zr', 'Hf', 'Eu', 'Ti', 'Gd', 'Tb',
    'Dy', 'Y', 'Ho', 'Er', 'Tm', 'Yb', 'Lu'
]

REE_ELEMENTS = ['La', 'Ce', 'Pr', 'Nd', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu']

CUSTOM_XY_ELEMENTS = [
    '1 (none)', 'Ag', 'Al', 'Al2O3', 'As', 'Au', 'B', 'Ba', 'Bi', 'Ca', 'CaO',
    'Cd', 'Ce', 'Co', 'Cr', 'Cr2O3', 'Cs', 'Cu', 'Dy', 'Er', 'Eu', 'F', 'Fe',
    'Fe2O3', 'FeO', 'Ga', 'Gd', 'Ge', 'Hf', 'Ho', 'K', 'K2O', 'La', 'Lu',
    'Mg#', 'Mg', 'MgO', 'Mn', 'MnO', 'Mo', 'Na', 'Na2O', 'Nb', 'Nd', 'Ni',
    'NiO', 'P', 'P2O5', 'Pb', 'Pr', 'Rb', 'S', 'Sb', 'Sc', 'Se', 'Si', 'SiO2',
    'Sm', 'Sn', 'Sr', 'Ta', 'Tb', 'Th', 'Ti', 'TiO2', 'Tm', 'U', 'V', 'W',
    'Y', 'Yb', 'Zn', 'Zr'
]

MW_MGO = 40.304
MW_FEO = 71.844


# =============================================================================
# UNIT & OXIDE CONVERSION UTILITIES
# =============================================================================
# Molar masses (g/mol, IUPAC standard atomic weights) for elements that are
# commonly reported as an oxide wt% in whole-rock geochemistry, used to
# convert between elemental (ppm) and oxide (wt%) concentrations.
ELEMENT_MOLAR_MASS = {
    'Si': 28.085, 'Ti': 47.867, 'Al': 26.982, 'Fe': 55.845, 'Mn': 54.938,
    'Mg': 24.305, 'Ca': 40.078, 'Na': 22.990, 'K': 39.098, 'P': 30.974,
    'Cr': 51.996, 'Ni': 58.693, 'O': 15.999,
}

# oxide formula -> (element symbol, atoms of element, atoms of oxygen)
OXIDE_COMPOSITION = {
    'SiO2': ('Si', 1, 2), 'TiO2': ('Ti', 1, 2), 'Al2O3': ('Al', 2, 3),
    'Fe2O3': ('Fe', 2, 3), 'FeO': ('Fe', 1, 1), 'MnO': ('Mn', 1, 1),
    'MgO': ('Mg', 1, 1), 'CaO': ('Ca', 1, 1), 'Na2O': ('Na', 2, 1),
    'K2O': ('K', 2, 1), 'P2O5': ('P', 2, 5), 'Cr2O3': ('Cr', 2, 3),
    'NiO': ('Ni', 1, 1),
}

# Element -> its most common oxide form in whole-rock geochemistry reporting.
ELEMENT_TO_OXIDE = {element: oxide for oxide, (element, _, _) in OXIDE_COMPOSITION.items()
                    # Fe maps to Fe2O3 (total iron) by convention; FeO stays reachable via OXIDE_COMPOSITION.
                    if not (oxide == 'FeO')}


def _oxide_element_mass_fraction(oxide):
    """Fraction of an oxide's molar mass contributed by its element."""
    element, n_el, n_o = OXIDE_COMPOSITION[oxide]
    element_mass = n_el * ELEMENT_MOLAR_MASS[element]
    oxide_mass = element_mass + n_o * ELEMENT_MOLAR_MASS['O']
    return element_mass / oxide_mass


def oxide_pct_to_element_ppm(oxide, wt_pct):
    """Convert oxide wt% (e.g. TiO2) to elemental ppm (e.g. Ti)."""
    return wt_pct * _oxide_element_mass_fraction(oxide) * 10000.0


def element_ppm_to_oxide_pct(oxide, ppm):
    """Convert elemental ppm (e.g. Ti) to the corresponding oxide wt% (e.g. TiO2)."""
    return (ppm / 10000.0) / _oxide_element_mass_fraction(oxide)


_PPB_UNIT_MARKERS = ('_PPB', '(PPB)', '[PPB]')
_PPM_UNIT_MARKERS = ('_PPM', '(PPM)', '[PPM]')
_PCT_UNIT_MARKERS = ('_PCT', '_WTPCT', '_WT_PCT', '_WT%', '(PCT)', '(WT%)', '%')


def _field_unit_hint(field_name):
    """Guess a field's stored unit ('ppb'/'ppm'/'pct') from its name, or
    None if the name carries no recognisable unit marker."""
    upper = field_name.upper()
    if any(marker in upper for marker in _PPB_UNIT_MARKERS):
        return 'ppb'
    if any(marker in upper for marker in _PPM_UNIT_MARKERS):
        return 'ppm'
    if any(marker in upper for marker in _PCT_UNIT_MARKERS) or upper.endswith('_WT'):
        return 'pct'
    return None


def _value_to_ppm(raw_value, field_name, default_unit='ppm'):
    """Convert a raw stored value to ppm, guessing its unit from the field name."""
    unit = _field_unit_hint(field_name) or default_unit
    if unit == 'ppb':
        return raw_value * 0.001
    if unit == 'pct':
        return raw_value * 10000.0
    return raw_value


def _value_to_pct(raw_value, field_name, default_unit='pct'):
    """Convert a raw stored value to wt%, guessing its unit from the field name."""
    unit = _field_unit_hint(field_name) or default_unit
    if unit == 'ppb':
        return raw_value * 1e-7
    if unit == 'ppm':
        return raw_value * 1e-4
    return raw_value


# =============================================================================
# FIELD NAME MATCHING UTILITIES
# =============================================================================
import re

def find_element_field(layer, element, allow_oxide_forms=True):
    """Find the field name in a layer that corresponds to a given element.

    `allow_oxide_forms=False` restricts the search to fields that plausibly
    report `element` itself (elemental if `element` is a plain symbol, or
    the given oxide if `element` is an oxide formula), without falling back
    to chemically-related alternate forms. This is used by the unit-aware
    value getters below, which perform their own explicit elemental<->oxide
    conversion instead of silently substituting one for the other.
    """
    field_names = [f.name() for f in layer.fields()]
    element_upper = element.upper()

    patterns = [
        element, element.upper(), element.lower(), element.capitalize(),
        f"{element}_ppm", f"{element.upper()}_ppm", f"{element.lower()}_ppm",
        f"{element}_PPM", f"{element.upper()}_PPM", f"{element.lower()}_PPM",
        f"{element}_ppb", f"{element.upper()}_ppb", f"{element}_PPB",
        f"{element}_pct", f"{element.upper()}_pct", f"{element}_PCT",
        f"{element}_wt", f"{element}_WT", f"{element}_wtpct", f"{element}_wt_pct",
        f"{element}(ppm)", f"{element} (ppm)", f"{element}(PPM)", f"{element}_[ppm]",
    ]

    oxide_forms = {
        'Ti': ['TiO2_pct', 'TiO2_PCT', 'TiO2_wt', 'TiO2', 'tio2_pct', 'TIO2_PCT'],
        'Fe': ['Fe2O3_pct', 'Fe2O3T_pct', 'FeO_pct', 'Fe2O3_PCT', 'FeOT_pct', 'FeO_PCT'],
        'Mn': ['MnO_pct', 'MnO_PCT', 'MnO_wt', 'MnO'],
        'Mg': ['MgO_pct', 'MgO_PCT', 'MgO_wt', 'MgO'],
        'Ca': ['CaO_pct', 'CaO_PCT', 'CaO_wt', 'CaO'],
        'Na': ['Na2O_pct', 'Na2O_PCT', 'Na2O_wt', 'Na2O'],
        'K': ['K2O_pct', 'K2O_PCT', 'K2O_wt', 'K2O'],
        'P': ['P2O5_pct', 'P2O5_PCT', 'P2O5_wt', 'P2O5'],
        'Si': ['SiO2_pct', 'SiO2_PCT', 'SiO2_wt', 'SiO2'],
        'Al': ['Al2O3_pct', 'Al2O3_PCT', 'Al2O3_wt', 'Al2O3'],
    }

    if allow_oxide_forms and element in oxide_forms:
        patterns.extend(oxide_forms[element])

    # 0. For single-character elements (Y, V, U, B, etc.), prefer Symbol_Fullname
    #    style FIRST to avoid matching bare coordinate/metadata fields like 'y' or 'v'.
    if len(element) == 1:
        pre_regex = re.compile(
            rf"^{re.escape(element)}_[A-Za-z]+$|"
            rf"^{re.escape(element.upper())}_[A-Za-z]+$",
            re.IGNORECASE
        )
        for field_name in field_names:
            if pre_regex.match(field_name):
                return field_name

    # 1. Exact pattern match
    for pattern in patterns:
        if pattern in field_names:
            return pattern

    # 2. Symbol_Fullname style match (e.g. Cl_Chlorine, K_Potassium, CA_Calcium)
    symbol_name_regex = re.compile(
        rf"^{re.escape(element)}_[A-Za-z]+$|"
        rf"^{re.escape(element.upper())}_[A-Za-z]+$|"
        rf"^{re.escape(element.lower())}_[A-Za-z]+$",
        re.IGNORECASE
    )
    for field_name in field_names:
        if symbol_name_regex.match(field_name):
            return field_name

    # 3. Fallback: uppercase prefix match with known unit suffixes. The
    # oxide-composition suffixes (e.g. element='Ti' matching 'TiO2_PCT')
    # are cross-form matches, so they're gated the same as oxide_forms/
    # oxide_to_base below.
    plain_suffixes = ['', '_PPM', '_PPB', '_PCT', '_WT', '_WTPCT',
                      '_WT_PCT', '(PPM)', ' (PPM)', '_[PPM]', '_WT%', 'PPM', 'PPB']
    oxide_suffixes = ['O2_PCT', 'O_PCT', '2O3_PCT', '2O_PCT', '2O5_PCT']
    allowed_remainders = plain_suffixes + (oxide_suffixes if allow_oxide_forms else [])
    for field_name in field_names:
        field_upper = field_name.upper()
        if field_upper.startswith(element_upper):
            remainder = field_upper[len(element_upper):]
            if remainder in allowed_remainders:
                return field_name

    if not allow_oxide_forms:
        return None

    # 4. For oxide lookups, fall back to the base element ppm field.
    # e.g. looking for 'TiO2' but only 'Ti_Titanium' (ppm) exists.
    # The caller (get_element_value) skips unit conversion when the returned
    # field name doesn't contain 'TIO2'/'MNO'/'P2O5', so ppm values are used as-is.
    oxide_to_base = {
        'TiO2': 'Ti', 'FeO': 'Fe', 'Fe2O3': 'Fe', 'MnO': 'Mn',
        'MgO': 'Mg', 'CaO': 'Ca', 'Na2O': 'Na', 'K2O': 'K',
        'P2O5': 'P', 'SiO2': 'Si', 'Al2O3': 'Al',
    }
    if element in oxide_to_base:
        base = oxide_to_base[element]
        base_upper = base.upper()
        # Symbol_Fullname style (e.g. Ti_Titanium)
        base_fn_re = re.compile(rf"^{re.escape(base)}_[A-Za-z]+$", re.IGNORECASE)
        for fn in field_names:
            if base_fn_re.match(fn):
                return fn
        # Plain element name or _ppm suffix
        for fn in field_names:
            fn_upper = fn.upper()
            if fn_upper in (base_upper, f"{base_upper}_PPM", f"{base_upper}_PPB"):
                return fn

    return None

def find_element_field_old(layer, element):
    """Find the field name in a layer that corresponds to a given element."""
    field_names = [f.name() for f in layer.fields()]
    element_upper = element.upper()
    
    patterns = [
        element, element.upper(), element.lower(), element.capitalize(),
        f"{element}_ppm", f"{element.upper()}_ppm", f"{element.lower()}_ppm",
        f"{element}_PPM", f"{element.upper()}_PPM", f"{element.lower()}_PPM",
        f"{element}_ppb", f"{element.upper()}_ppb", f"{element}_PPB",
        f"{element}_pct", f"{element.upper()}_pct", f"{element}_PCT",
        f"{element}_wt", f"{element}_WT", f"{element}_wtpct", f"{element}_wt_pct",
        f"{element}(ppm)", f"{element} (ppm)", f"{element}(PPM)", f"{element}_[ppm]",
    ]
    
    oxide_forms = {
        'Ti': ['TiO2_pct', 'TiO2_PCT', 'TiO2_wt', 'TiO2', 'tio2_pct', 'TIO2_PCT'],
        'Fe': ['Fe2O3_pct', 'Fe2O3T_pct', 'FeO_pct', 'Fe2O3_PCT', 'FeOT_pct', 'FeO_PCT'],
        'Mn': ['MnO_pct', 'MnO_PCT', 'MnO_wt', 'MnO'],
        'Mg': ['MgO_pct', 'MgO_PCT', 'MgO_wt', 'MgO'],
        'Ca': ['CaO_pct', 'CaO_PCT', 'CaO_wt', 'CaO'],
        'Na': ['Na2O_pct', 'Na2O_PCT', 'Na2O_wt', 'Na2O'],
        'K': ['K2O_pct', 'K2O_PCT', 'K2O_wt', 'K2O'],
        'P': ['P2O5_pct', 'P2O5_PCT', 'P2O5_wt', 'P2O5'],
        'Si': ['SiO2_pct', 'SiO2_PCT', 'SiO2_wt', 'SiO2'],
        'Al': ['Al2O3_pct', 'Al2O3_PCT', 'Al2O3_wt', 'Al2O3'],
    }
    
    if element in oxide_forms:
        patterns.extend(oxide_forms[element])

    for pattern in patterns:
        if pattern in field_names:
            return pattern

    for field_name in field_names:
        field_upper = field_name.upper()
        if field_upper.startswith(element_upper):
            remainder = field_upper[len(element_upper):]
            if remainder in ['', '_PPM', '_PPB', '_PCT', '_WT', '_WTPCT',
                           '_WT_PCT', '(PPM)', ' (PPM)', '_[PPM]', '_WT%', 'PPM', 'PPB',
                           'O2_PCT', 'O_PCT', '2O3_PCT', '2O_PCT', '2O5_PCT']:
                return field_name
    return None


def _read_numeric_field(feature, field_name):
    """Read a field's value as a float, or None if missing/non-numeric."""
    try:
        value = feature[field_name]
        if value is None or value == NULL:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def get_element_ppm(feature, layer, element):
    """Return `element`'s concentration in ppm (trace-element basis).

    Tries a field for the plain elemental symbol first (any unit - ppm,
    ppb or pct - auto-converted to ppm). If none is found and the element
    has a common oxide form (e.g. Ti -> TiO2), falls back to that oxide
    field and converts oxide wt% to elemental ppm via its molar mass.
    """
    field_name = find_element_field(layer, element, allow_oxide_forms=False)
    if field_name is not None:
        raw = _read_numeric_field(feature, field_name)
        if raw is not None:
            return _value_to_ppm(raw, field_name, default_unit='ppm')

    oxide = ELEMENT_TO_OXIDE.get(element)
    if oxide is not None:
        oxide_field = find_element_field(layer, oxide, allow_oxide_forms=False)
        if oxide_field is not None:
            raw = _read_numeric_field(feature, oxide_field)
            if raw is not None:
                pct = _value_to_pct(raw, oxide_field, default_unit='pct')
                return oxide_pct_to_element_ppm(oxide, pct)
    return None


def get_oxide_pct(feature, layer, oxide):
    """Return `oxide`'s concentration in wt%.

    Tries a field for the oxide formula first (any unit - ppm, ppb or pct
    - auto-converted to wt%). If none is found, falls back to the
    corresponding elemental field and converts elemental ppm/pct to oxide
    wt% via its molar mass.
    """
    field_name = find_element_field(layer, oxide, allow_oxide_forms=False)
    if field_name is not None:
        raw = _read_numeric_field(feature, field_name)
        if raw is not None:
            return _value_to_pct(raw, field_name, default_unit='pct')

    composition = OXIDE_COMPOSITION.get(oxide)
    if composition is not None:
        element = composition[0]
        elem_field = find_element_field(layer, element, allow_oxide_forms=False)
        if elem_field is not None:
            raw = _read_numeric_field(feature, elem_field)
            if raw is not None:
                ppm = _value_to_ppm(raw, elem_field, default_unit='ppm')
                return element_ppm_to_oxide_pct(oxide, ppm)
    return None


def get_element_value(feature, layer, element, convert_to_ppm=True):
    """Get the value of an element (in ppm) or a recognised oxide formula
    (in wt%) from a feature, auto-converting between ppm/ppb/pct and
    elemental/oxide forms depending on what is actually stored in the layer.

    `convert_to_ppm=False` returns the field's raw stored value unconverted.
    """
    if not convert_to_ppm:
        field_name = find_element_field(layer, element)
        if field_name is None:
            return None
        return _read_numeric_field(feature, field_name)
    if element in OXIDE_COMPOSITION:
        return get_oxide_pct(feature, layer, element)
    return get_element_ppm(feature, layer, element)


def get_available_elements(layer, element_list):
    """Check which elements from a list are available in the layer."""
    found = {}
    not_found = []
    for element in element_list:
        field_name = find_element_field(layer, element)
        if field_name:
            found[element] = field_name
        else:
            not_found.append(element)
    return found, not_found


def get_custom_element_value(feature, layer, element_name, normalize=False, norm_values=None):
    """Get element/oxide value for custom XY plots."""
    if element_name == '1 (none)':
        return 1.0
    
    if element_name == 'Mg#':
        mgo_field = find_element_field(layer, 'MgO')
        feo_field = find_element_field(layer, 'FeO')
        
        if feo_field is None:
            feo_field = find_element_field(layer, 'FeOT')
        if feo_field is None:
            fe2o3_field = find_element_field(layer, 'Fe2O3')
            if fe2o3_field:
                try:
                    fe2o3_val = float(feature[fe2o3_field])
                    if fe2o3_val is None or fe2o3_val == NULL:
                        return None
                    feo_val = fe2o3_val * 0.8998
                except (ValueError, TypeError):
                    return None
            else:
                return None
        else:
            try:
                feo_val = float(feature[feo_field])
                if feo_val is None or feo_val == NULL:
                    return None
            except (ValueError, TypeError):
                return None
        
        if mgo_field is None:
            return None
            
        try:
            mgo_val = float(feature[mgo_field])
            if mgo_val is None or mgo_val == NULL:
                return None
            
            mg_molar = mgo_val / MW_MGO
            fe_molar = 0.9 * feo_val / MW_FEO
            
            if (mg_molar + fe_molar) <= 0:
                return None
            
            mg_number = 100 * mg_molar / (mg_molar + fe_molar)
            return mg_number
        except (ValueError, TypeError, ZeroDivisionError):
            return None
    
    # Recognised element symbols are returned in ppm and recognised oxide
    # formulas in wt%, auto-converting from whichever unit/form (ppm, ppb,
    # pct, elemental or oxide) the layer actually stores. A field picked
    # directly via "show all numeric fields" isn't a known species, so it's
    # returned as stored, with no conversion.
    if element_name in OXIDE_COMPOSITION:
        value = get_oxide_pct(feature, layer, element_name)
    elif element_name in CUSTOM_XY_ELEMENTS:
        value = get_element_ppm(feature, layer, element_name)
    else:
        field_name = find_element_field(layer, element_name)
        if field_name is None:
            return None
        value = _read_numeric_field(feature, field_name)

    if value is None:
        return None

    if normalize and norm_values and element_name in norm_values:
        norm_val = norm_values.get(element_name)
        if norm_val and norm_val > 0:
            value = value / norm_val

    return value


# =============================================================================
# BUBBLE SIZE SCALING UTILITIES
# =============================================================================
import math

BUBBLE_SCALE_METHODS = {'Linear': 'linear', 'Log10': 'log10', 'Exponential': 'exponential'}


def bubble_size_fraction(value, vmin, vmax, method='linear'):
    """Return `value`'s position in [0, 1] between vmin and vmax, using the
    chosen scaling curve.

    'linear' interpolates in value-space; 'log10' interpolates in log-space
    (equal ratios map to equal steps, suited to data spanning orders of
    magnitude) and requires positive values; 'exponential' grows size
    increasingly fast as value approaches vmax, emphasising the largest
    values.
    """
    if vmax <= vmin:
        return 1.0
    if method == 'log10':
        if value is None or value <= 0 or vmin <= 0 or vmax <= 0:
            return 0.0
        lo, hi, v = math.log10(vmin), math.log10(vmax), math.log10(value)
        if hi <= lo:
            return 1.0
        t = (v - lo) / (hi - lo)
    elif method == 'exponential':
        linear_t = (value - vmin) / (vmax - vmin)
        k = 3.0
        t = (math.exp(k * linear_t) - 1.0) / (math.exp(k) - 1.0)
    else:
        t = (value - vmin) / (vmax - vmin)
    return max(0.0, min(1.0, t))


def bubble_symbol_size(value, vmin, vmax, min_size, max_size, method='linear'):
    """Map `value` to a marker size (matplotlib scatter `s`, in points²)
    between min_size and max_size, using the chosen scaling curve."""
    t = bubble_size_fraction(value, vmin, vmax, method)
    return min_size + t * (max_size - min_size)


# =============================================================================
# TERNARY PLOT UTILITIES
# =============================================================================

def ternary_to_cartesian(a, b, c):
    """Convert ternary coordinates (a, b, c) to Cartesian (x, y)."""
    total = a + b + c
    if total == 0:
        return np.nan, np.nan
    a, b, c = a/total, b/total, c/total
    x = 0.5 * (2 * b + c)
    y = (np.sqrt(3) / 2) * c
    return x, y


def plot_ternary_axes(ax, labels):
    """Draw ternary diagram axes with labels at apexes."""
    vertices = np.array([[0, 0], [1, 0], [0.5, np.sqrt(3)/2], [0, 0]])
    ax.plot(vertices[:, 0], vertices[:, 1], 'k-', linewidth=1.5)
    ax.text(0, -0.05, labels[0], ha='center', va='top', fontsize=11, fontweight='bold')
    ax.text(1, -0.05, labels[1], ha='center', va='top', fontsize=11, fontweight='bold')
    ax.text(0.5, np.sqrt(3)/2 + 0.05, labels[2], ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    for i in [20, 40, 60, 80]:
        t = i / 100
        x1, y1 = ternary_to_cartesian(100-i, 0, i)
        x2, y2 = ternary_to_cartesian(0, 100-i, i)
        ax.plot([x1, x2], [y1, y2], 'gray', linewidth=0.5, alpha=0.3)
        x1, y1 = ternary_to_cartesian(100-i, i, 0)
        x2, y2 = ternary_to_cartesian(0, i, 100-i)
        ax.plot([x1, x2], [y1, y2], 'gray', linewidth=0.5, alpha=0.3)
        x1, y1 = ternary_to_cartesian(i, 100-i, 0)
        x2, y2 = ternary_to_cartesian(i, 0, 100-i)
        ax.plot([x1, x2], [y1, y2], 'gray', linewidth=0.5, alpha=0.3)

    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-0.15, np.sqrt(3)/2 + 0.1)
    ax.set_aspect('equal')
    ax.axis('off')


def draw_ternary_line(ax, point1, point2, **kwargs):
    """Draw a line between two ternary coordinates."""
    x1, y1 = ternary_to_cartesian(*point1)
    x2, y2 = ternary_to_cartesian(*point2)
    ax.plot([x1, x2], [y1, y2], **kwargs)


def ternary_text(ax, a, b, c, text, **kwargs):
    """Place text at a ternary coordinate."""
    x, y = ternary_to_cartesian(a, b, c)
    ax.text(x, y, text, **kwargs)


# =============================================================================
# DISCRIMINATION DIAGRAMS
# =============================================================================

def _scatter_grouped(ax, data, fids, sample_names, sample_colors, sample_markers,
                     show_category_legend, category_colors, sample_sizes=None):
    """One ax.scatter() call per category group instead of one per point.

    Handles both binary (x, y) and ternary (a, b, c) coordinate tuples.
    `sample_sizes`, if given, is a per-sample list of marker areas (points^2,
    matplotlib scatter `s` units) aligned with `sample_names`/`data`, used
    for bubble-size plots; otherwise every point uses a fixed default size.
    Returns ({fid: (PathCollection, local_index)}, {category: [PathCollection, ...]})
    for use by apply_selection() and the interactive category styling panel.
    """
    default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
    fid_iter = iter(fids)
    cat_groups = {}

    for i, (coords, name) in enumerate(zip(data, sample_names)):
        if len(coords) == 3:
            if any(v is None for v in coords):
                continue
            x, y = ternary_to_cartesian(*coords)
        else:
            x, y = coords[0], coords[1]
            if x is None or y is None:
                continue
        fid = next(fid_iter)
        color  = sample_colors[i]  if i < len(sample_colors)  else sample_colors[i  % len(sample_colors)]
        marker = sample_markers[i] if sample_markers           else default_markers[i % len(default_markers)]
        size = sample_sizes[i] if sample_sizes and i < len(sample_sizes) else 80
        cat_key = (name, marker) if sample_markers else name
        if cat_key not in cat_groups:
            cat_groups[cat_key] = {'xs': [], 'ys': [], 'fids': [], 'colors': [], 'sizes': [],
                                   'marker': marker, 'name': name}
        g = cat_groups[cat_key]
        g['xs'].append(x);  g['ys'].append(y)
        g['fids'].append(fid);  g['colors'].append(color); g['sizes'].append(size)

    plotted_names = set()
    fid_to_scatter = {}
    category_artists = {}
    for g in cat_groups.values():
        label = None
        if show_category_legend and category_colors and g['name'] not in plotted_names:
            label = g['name']
            plotted_names.add(g['name'])
        sc = ax.scatter(g['xs'], g['ys'], marker=g['marker'], s=g['sizes'], c=g['colors'],
                        edgecolors='black', linewidths=0.5, zorder=10, label=label)
        category_artists.setdefault(g['name'], []).append(sc)
        for local_idx, fid in enumerate(g['fids']):
            fid_to_scatter[fid] = (sc, local_idx)
    return fid_to_scatter, category_artists

class PolygonDiagramMixin:
    """Shared classify_point and draw_fields for diagram classes that define _get_fields().

    _get_fields() must return a list of dicts, each with keys:
      'name', 'position', 'fontsize', 'ha', 'va', 'fontweight',
      'rotation', 'color', 'x', 'y'
    Polygons are open (first vertex != last vertex).
    Fields named 'void' are drawn but not labelled, and classify as ''.
    """

    @classmethod
    def classify_point(cls, x, y):
        if x is None or y is None:
            return None
        for f in cls._get_fields():
            xs = f['x'] + [f['x'][0]]
            ys = f['y'] + [f['y'][0]]
            if Path(list(zip(xs, ys))).contains_point((x, y)):
                name = f['name']
                return name if name != 'void' else ''
        return None

    @classmethod
    def draw_fields(cls, ax):
        for f in cls._get_fields():
            ax.plot(f['x'], f['y'], 'k-', linewidth=1.0)
            if f['name'] != 'void':
                pos = f['position']
                label_text = f['name'].replace('-', '\n').replace(' ', '\n')
                ax.text(pos[0], pos[1], label_text,
                        fontsize=f['fontsize'], ha=f['ha'], va=f['va'],
                        fontweight=f['fontweight'], rotation=f.get('rotation', 0),
                        color=f.get('color', 'k'))


class Pearce1996_NbY_ZrTi(PolygonDiagramMixin):
    """Nb/Y vs Zr/Ti diagram (Winchester & Floyd 1977; Pearce 1996)."""

    name = "Zr/Ti vs Nb/Y"
    reference = "Pearce (1996)"
    field_name = "Pearce96Nb"

    @classmethod
    def _get_fields(cls):
        """Return field polygon definitions with label attributes and open polygon vertices."""
        return [
            {'name': 'Basalt',
             'position': [0.1, 0.006],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.01, 0.7, 0.7, 0.01],
             'y': [0.001, 0.001, 0.03, 0.008]},
            {'name': 'Andesite Basaltic andesite',
             'position': [0.1, 0.025],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.01, 0.7, 0.7, 0.01],
             'y': [0.008, 0.03, 0.115, 0.03]},
            {'name': 'Rhyolite-Dacite',
             'position': [0.1, 0.15],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.01, 0.7, 0.7, 0.1, 0.01],
             'y': [0.03, 0.115, 0.3, 1.0, 1.0]},
            {'name': 'Trachyte',
             'position': [1.8, 0.2],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.7, 3.5, 3.5, 0.7],
             'y': [0.115, 0.195, 0.74, 0.3]},
            {'name': 'Trachy-andesite',
             'position': [1.8, 0.065],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.7, 3.5, 3.5, 0.7],
             'y': [0.03, 0.05, 0.195, 0.115]},
            {'name': 'Alkali basalt',
             'position': [1.8, 0.015],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.7, 3.5, 3.5, 0.7],
             'y': [0.001, 0.001, 0.05, 0.03]},
            {'name': 'Alkali rhyolite',
             'position': [0.7, 0.6],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.1, 0.7, 6.0],
             'y': [1.0, 0.3, 1.0]},
            {'name': 'Phonolite',
             'position': [5.0, 0.4],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [10, 3.5, 3.5, 6, 10],
             'y': [0.27, 0.195, 0.74, 1.0, 1.0]},
            {'name': 'Tephri-phonolite',
             'position': [5.0, 0.09],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [10, 3.5, 3.5, 10],
             'y': [0.07, 0.05, 0.195, 0.27]},
            {'name': 'Foidite',
             'position': [5.0, 0.02],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [10, 3.5, 3.5, 10],
             'y': [0.001, 0.001, 0.05, 0.07]},
        ]

    @classmethod
    def classify_point(cls, x, y):
        """Return field name for point (x=Nb/Y, y=Zr/Ti) in log space, or None if outside all fields."""
        import math
        if x is None or y is None or x <= 0 or y <= 0:
            return None
        lx, ly = math.log10(x), math.log10(y)
        for f in cls._get_fields():
            log_xs = [math.log10(v) for v in f['x']] + [math.log10(f['x'][0])]
            log_ys = [math.log10(v) for v in f['y']] + [math.log10(f['y'][0])]
            if Path(list(zip(log_xs, log_ys))).contains_point((lx, ly)):
                name = f['name']
                return name if name != 'void' else ''
        return None

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        zr = get_element_value(feature, layer, 'Zr')
        ti = get_element_value(feature, layer, 'Ti')
        nb = get_element_value(feature, layer, 'Nb')
        y = get_element_value(feature, layer, 'Y')
        
        if all(v is not None and v > 0 for v in [zr, ti, nb, y]):
            return nb/y, zr/ti
        return None, None

    @classmethod
    def draw_fields(cls, ax):
        super().draw_fields(ax)
        ax.text(0.12, 0.0015, 'subalkaline', fontsize=9, ha='center', va='top')
        ax.text(1.8, 0.0015, 'alkaline', fontsize=9, ha='center', va='top')
        ax.text(6, 0.0015, 'ultra-\nalkaline', fontsize=8, ha='center', va='top')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None, sample_sizes=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter, category_artists = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors,
                                          sample_sizes=sample_sizes)
        
        ax.set_xlabel('Nb/Y', fontsize=12)
        ax.set_ylabel('Zr/Ti', fontsize=12)
        n_str = f' (n={n_samples})' if n_samples is not None else ''
        ax.set_title(f'{cls.name}{n_str}\n{cls.reference}', fontsize=11)
        ax.set_xlim(0.01, 10)
        ax.set_ylim(0.001, 1)
        
        if show_category_legend and category_colors and len(category_colors) > 0:
            n_categories = len(category_colors)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=8,
                     ncol=ncol, framealpha=0.9, borderaxespad=0.)
        return fid_to_scatter, category_artists


class Winchester_Floyd1977_NbY_ZrTi(PolygonDiagramMixin):
    """Nb/Y vs Zr/Ti diagram (Winchester & Floyd 1977)."""

    name = "Zr/Ti vs Nb/Y"
    reference = "Winchester & Floyd (1977)"
    field_name = "WF1977_NbY"

    @classmethod
    def _get_fields(cls):
        """Return field polygon definitions with label attributes and open polygon vertices."""
        return [
            {'name': 'Andesite Basalt',
            'position': [0.1, 0.007],
            'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
            'rotation': 0, 'color': 'k',
            'x': [0.029, 0.172, 0.181, 0.19, 0.211, 0.234, 0.264, 0.287, 0.344, 0.412, 0.494, 0.405, 0.332,  0.239,0.15,0.095,0.06 ], 
            'y': [0.005, 0.005, 0.005, 0.005,0.006, 0.007, 0.008, 0.009, 0.011, 0.013, 0.015,0.014, 0.013, 0.012, 0.012,0.012,0.012]},
            {'name': 'Rhyodacite-Dacite',
             'position': [0.1, 0.07],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.021, 0.311, 0.374, 0.450, 0.542, 0.652, 0.652, 0.665, 0.687, 0.027],
             'y': [0.061, 0.027, 0.026, 0.026, 0.026, 0.026, 0.069, 0.078, 0.085, 0.213]},
            {'name': 'Andesite',
             'position': [0.1, 0.02],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.06, 0.095, 0.150, 0.239,  0.332, 0.405, 0.494, 0.568, 0.652, 0.652, 0.652, 0.542, 0.450, 0.374, 0.311, 0.021],
             'y': [0.012, 0.012, 0.012, 0.012,  0.013, 0.014, 0.015, 0.017, 0.019, 0.027, 0.026, 0.026, 0.026, 0.026, 0.027, 0.061]},
            {'name': 'Rhyolite',
             'position': [0.3, 0.2],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.027, 0.687, 0.95, 0.317],
             'y': [0.213, 0.085, 0.136, 0.704]},
            {'name': 'Trachyte',
             'position': [3.5, 0.1],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [9.675, 7.980, 6.590, 5.440, 4.490, 3.710, 3.250, 2.790, 2.446, 2.215, 2.073, 1.979, 1.760, 1.451, 1.400, 1.318, 1.220, 5.516, 10.0],
             'y': [0.148, 0.160, 0.175, 0.196, 0.224, 0.261, 0.298, 0.359, 0.433, 0.522, 0.630, 0.760, 1.365, 0.167, 0.137, 0.113, 0.095, 0.038, 0.038]},
            {'name': 'Trachy-andesite',
             'position': [1.6, 0.04],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.652, 0.652, 0.652, 0.665, 0.687, 0.95, 1.22, 5.516, 4.962, 4.319, 3.637, 2.944, 2.579, 2.260, 1.980, 1.735, 1.520, 1.332, 1.182, 1.050, 0.932, 0.827, 0.735, 0.652],
             'y': [0.019, 0.027, 0.069, 0.078, 0.085, 0.136, 0.095, 0.038, 0.031, 0.024, 0.020, 0.016, 0.018, 0.020, 0.021, 0.023, 0.024, 0.024, 0.024, 0.023, 0.022, 0.021, 0.020, 0.019]},
            {'name': 'Alkali basalt',
             'position': [1.3, 0.007],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.652, 0.652, 0.735, 0.827, 0.932, 1.050, 1.182, 1.332, 1.520, 1.735, 1.980, 2.260, 2.579, 2.944, 2.867],
             'y': [0.002, 0.019, 0.020, 0.021, 0.022, 0.023, 0.024, 0.024, 0.024, 0.023, 0.021, 0.020, 0.018, 0.016, 0.004]},
            {'name': 'Comendite',
             'position': [0.8, 0.4],
             'fontsize': 12, 'ha': 'cente'
             'r', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [1.510, 1.760, 1.760, 1.451, 1.400, 1.318, 1.220, 0.950, 0.317],
             'y': [3.022, 1.365, 1.365, 0.167, 0.137, 0.113, 0.095, 0.136, 0.704]},
            {'name': 'Phonolite',
             'position': [5.0, 0.4],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [9.675, 7.980, 6.590, 5.440, 4.490, 3.710, 3.250, 2.790, 2.446, 2.215, 2.073, 1.979, 1.760, 1.510, 10.0],
             'y': [0.148, 0.160, 0.175, 0.196, 0.224, 0.261, 0.298, 0.359, 0.433, 0.522, 0.630, 0.760, 1.365, 1.0, 1.0]},
            {'name': 'Basanite',
             'position': [5.3, 0.007],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [10.0, 5.516, 4.319, 2.944, 2.867],
             'y': [0.038, 0.038, 0.024, 0.016, 0.004]},
            {'name': 'Sub-alkaline basalt',
             'position': [0.1, 0.003],
             'fontsize': 12, 'ha': 'center', 'va': 'top', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.029, 0.172, 0.172, 0.181, 0.190, 0.211, 0.234, 0.264, 0.287, 0.344, 0.412, 0.494, 0.568, 0.652, 0.652],
             'y': [0.001, 0.001, 0.005, 0.005, 0.005, 0.006, 0.007, 0.008, 0.009, 0.011, 0.013, 0.015, 0.017, 0.019, 0.002]},
        ]

    @classmethod
    def classify_point(cls, x, y):
        """Return field name for point (x=Nb/Y, y=Zr/Ti) in log space, or None if outside all fields."""
        import math
        if x is None or y is None or x <= 0 or y <= 0:
            return None
        lx, ly = math.log10(x), math.log10(y)
        for f in cls._get_fields():
            log_xs = [math.log10(v) for v in f['x']] + [math.log10(f['x'][0])]
            log_ys = [math.log10(v) for v in f['y']] + [math.log10(f['y'][0])]
            if Path(list(zip(log_xs, log_ys))).contains_point((lx, ly)):
                name = f['name']
                return name if name != 'void' else ''
        return None

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        zr = get_element_value(feature, layer, 'Zr')
        ti = get_element_value(feature, layer, 'Ti')
        nb = get_element_value(feature, layer, 'Nb')
        y = get_element_value(feature, layer, 'Y')

        if all(v is not None and v > 0 for v in [zr, ti, nb, y]):
            return nb/y, zr/ti
        return None, None

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None, sample_sizes=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter, category_artists = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors,
                                          sample_sizes=sample_sizes)
        
        ax.set_xlabel('Nb/Y', fontsize=12)
        ax.set_ylabel('Zr/Ti', fontsize=12)
        n_str = f' (n={n_samples})' if n_samples is not None else ''
        ax.set_title(f'{cls.name}{n_str}\n{cls.reference}', fontsize=11)
        ax.set_xlim(0.01, 10)
        ax.set_ylim(0.001, 1)
        
        if show_category_legend and category_colors and len(category_colors) > 0:
            n_categories = len(category_colors)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=8,
                     ncol=ncol, framealpha=0.9, borderaxespad=0.)
        return fid_to_scatter, category_artists


class Meschede1986_Ternary(PolygonDiagramMixin):
    """Zr/4-Nb*2-Y ternary diagram (Meschede, 1986)."""

    name = "Zr/4 - Nb×2 - Y"
    reference = "Meschede (1986)"
    field_name = "Mesch1986"

    @classmethod
    def _get_fields(cls):
        return [
            {'name': 'AI',
             'position': [0.45, 0.5],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.34, 0.41, 0.56, 0.47, 0.31, 0.34],
             'y': [0.09, 0.42, 0.49, 0.68, 0.32, 0.09]
            },
            {'name': 'AII',
             'position': [0.45, 0.35],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.34, 0.46, 0.58, 0.56, 0.41, 0.34],
            'y': [0.09, 0.3, 0.43, 0.49, 0.42, 0.09]
            },
            {'name': 'B',
             'position': [0.55, 0.3],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.69, 0.51, 0.46, 0.58, 0.69],
             'y': [0.19, 0.2, 0.3, 0.43, 0.19]
            },
            {'name': 'C',
             'position': [0.42, 0.15],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.45, 0.34, 0.46, 0.51, 0.45],
             'y': [0.03, 0.09, 0.3, 0.2, 0.03]},
            {'name': 'D',
             'position': [0.6, 0.07],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [0.5, 0.45, 0.51, 0.69, 0.77],
             'y': [-0.0, 0.03, 0.2, 0.19, 0.0]}
        ]

    @classmethod
    def classify_point(cls, a, b, c):
        if a is None or b is None or c is None:
            return None
        if a + b + c <= 0:
            return None
        x, y = ternary_to_cartesian(a, b, c)
        for f in cls._get_fields():
            xs = f['x'] + [f['x'][0]]
            ys = f['y'] + [f['y'][0]]
            if Path(list(zip(xs, ys))).contains_point((x, y)):
                name = f['name']
                return name if name != 'void' else ''
        return None

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        zr = get_element_value(feature, layer, 'Zr')
        nb = get_element_value(feature, layer, 'Nb')
        y = get_element_value(feature, layer, 'Y')

        if all(v is not None and v >= 0 for v in [zr, nb, y]):
            return zr/4, y, nb*2
        return None, None, None

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None, sample_sizes=None):
        plot_ternary_axes(ax, labels=['Zr/4', 'Y', 'Nb×2'])
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter, category_artists = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors,
                                          sample_sizes=sample_sizes)
        
        n_str = f' (n={n_samples})' if n_samples is not None else ''
        ax.set_title(f'{cls.name}{n_str}\n{cls.reference}', fontsize=11)
        
        if show_category_legend and category_colors and len(category_colors) > 0:
            n_categories = len(category_colors)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.08), fontsize=8,
                     ncol=ncol, framealpha=0.9, borderaxespad=0.)
        
        if show_legend:
            legend_text = "AI, AII = WP alkali basalts\nB = P-type MORB\nC = VAB\nD = N-type MORB"
            ax.text(0.9, 0.5, legend_text, transform=ax.transAxes, fontsize=8,
                   verticalalignment='center', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        return fid_to_scatter, category_artists


class Pearce1984_YNb:
    """Nb vs Y diagram for granites (Pearce et al., 1984)."""

    name = "Nb vs Y"
    reference = "Pearce et al. (1984)"
    field_name = "Pearce84_Y"

    @classmethod
    def classify_point(cls, x, y):
        """Return tectonic field for point (x=Y ppm, y=Nb ppm)."""
        import math
        if x is None or y is None or x <= 0 or y <= 0:
            return None
        lx, ly = math.log10(x), math.log10(y)
        # V-shaped boundary: left arm (1,2000)→(50,10), right arm (50,10)→(1000,100)
        left_slope = (math.log10(10) - math.log10(2000)) / (math.log10(50) - math.log10(1))
        right_slope = (math.log10(100) - math.log10(10)) / (math.log10(1000) - math.log10(50))
        if x <= 50:
            boundary_ly = math.log10(2000) + left_slope * (lx - math.log10(1))
            if ly > boundary_ly:
                return 'WPG'
            else:
                return 'VAG + syn-COLG'
        else:
            boundary_ly = math.log10(10) + right_slope * (lx - math.log10(50))
            if ly > boundary_ly:
                return 'WPG'
            else:
                return 'ORG'

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        nb = get_element_value(feature, layer, 'Nb')
        y = get_element_value(feature, layer, 'Y')
        
        if nb is not None and y is not None and nb > 0 and y > 0:
            return y, nb
        return None, None

    @classmethod
    def draw_fields(cls, ax):
        ax.plot([1, 50], [2000, 10], 'k-', linewidth=1.5)
        ax.plot([50, 40], [10, 1], 'k-', linewidth=1.5)
        ax.plot([50, 1000], [10, 100], 'k-', linewidth=1.5)
        ax.plot([30, 1000], [20, 300], 'k--', linewidth=1.5)
        
        ax.text(6, 3, 'VAG +\nsyn-COLG', fontsize=12, ha='center', va='center')
        ax.text(200, 600, 'WPG', fontsize=12, ha='center', va='center')
        ax.text(200, 7, 'ORG', fontsize=12, ha='center', va='center')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None, sample_sizes=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter, category_artists = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors,
                                          sample_sizes=sample_sizes)
        
        ax.set_xlabel('Y (ppm)', fontsize=12)
        ax.set_ylabel('Nb (ppm)', fontsize=12)
        n_str = f' (n={n_samples})' if n_samples is not None else ''
        ax.set_title(f'{cls.name}{n_str}\n{cls.reference}', fontsize=11)
        ax.set_xlim(1, 1000)
        ax.set_ylim(1, 2000)
        
        if show_category_legend and category_colors and len(category_colors) > 0:
            n_categories = len(category_colors)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=8,
                     ncol=ncol, framealpha=0.9, borderaxespad=0.)
        
        if show_legend:
            legend_text = "VAG = Volcanic arc granites\nsyn-COLG = Syn-collision granites\nWPG = Within-plate granites\nORG = Ocean ridge granites"
            ax.text(0.98, 0.02, legend_text, transform=ax.transAxes, fontsize=8,
                   verticalalignment='bottom', horizontalalignment='right',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        return fid_to_scatter, category_artists


class Pearce1984_YNbRb:
    """Rb vs (Y+Nb) diagram for granites (Pearce et al., 1984)."""

    name = "Rb vs (Y+Nb)"
    reference = "Pearce et al. (1984)"
    field_name = "Pearce84Rb"

    @classmethod
    def classify_point(cls, x, y):
        """Return tectonic field for point (x=Y+Nb ppm, y=Rb ppm)."""
        import math
        if x is None or y is None or x <= 0 or y <= 0:
            return None
        lx, ly = math.log10(x), math.log10(y)
        # Vertical boundary at x=50
        # Left (x<50): line (1,80)→(50,300) separates VAG (below) from syn-COLG (above)
        # Right (x>50): line (50,8)→(2000,400) separates ORG (below) from WPG (above)
        if x < 50:
            vag_slope = (math.log10(300) - math.log10(80)) / (math.log10(50) - math.log10(1))
            vag_ly = math.log10(80) + vag_slope * (lx - math.log10(1))
            return 'syn-COLG' if ly > vag_ly else 'VAG'
        else:
            wpg_slope = (math.log10(400) - math.log10(8)) / (math.log10(2000) - math.log10(50))
            wpg_ly = math.log10(8) + wpg_slope * (lx - math.log10(50))
            return 'WPG' if ly > wpg_ly else 'ORG'

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        y = get_element_value(feature, layer, 'Y')
        nb = get_element_value(feature, layer, 'Nb')
        rb = get_element_value(feature, layer, 'Rb')
        
        if all(v is not None and v > 0 for v in [y, nb, rb]):
            return y + nb, rb
        return None, None

    @classmethod
    def draw_fields(cls, ax):
        ax.plot([50, 50], [1, 300], 'k-', linewidth=1.5)
        ax.plot([50, 400], [300, 2000], 'k-', linewidth=1.5)
        ax.plot([1, 50], [80, 300], 'k-', linewidth=1.5)
        ax.plot([50, 2000], [8, 400], 'k-', linewidth=1.5)
        
        ax.text(8, 30, 'VAG', fontsize=12, ha='center', va='center')
        ax.text(12, 700, 'syn-COLG', fontsize=11, ha='center', va='center')
        ax.text(400, 200, 'WPG', fontsize=12, ha='center', va='center')
        ax.text(400, 20, 'ORG', fontsize=12, ha='center', va='center')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None, sample_sizes=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter, category_artists = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors,
                                          sample_sizes=sample_sizes)
        
        ax.set_xlabel('Y + Nb (ppm)', fontsize=12)
        ax.set_ylabel('Rb (ppm)', fontsize=12)
        n_str = f' (n={n_samples})' if n_samples is not None else ''
        ax.set_title(f'{cls.name}{n_str}\n{cls.reference}', fontsize=11)
        ax.set_xlim(1, 10000)
        ax.set_ylim(1, 10000)
        
        if show_category_legend and category_colors and len(category_colors) > 0:
            n_categories = len(category_colors)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=8,
                     ncol=ncol, framealpha=0.9, borderaxespad=0.)
        
        if show_legend:
            legend_text = "VAG = Volcanic arc granites\nSyn-COLG = Syn-collision granites\nWPG = Within-plate granites\nORG = Ocean ridge granites"
            ax.text(0.98, 0.02, legend_text, transform=ax.transAxes, fontsize=8,
                   verticalalignment='bottom', horizontalalignment='right',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        return fid_to_scatter, category_artists


class PearceCann1973_ZrTi(PolygonDiagramMixin):
    """Ti vs Zr diagram (Pearce & Cann, 1973)."""

    name = "Ti vs Zr"
    reference = "Pearce & Cann (1973)"
    field_name = "PC1973ZrTi"

    @classmethod
    def _get_fields(cls):
        return [
            {'name': 'MORB',
             'position': [87, 7500],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [110, 87.59, 69.57, 83.68, 109.68],
             'y': [9000, 9000, 7628.23, 6244.66, 8131.34]},
            {'name': 'CAB',
             'position': [93, 3500],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [109.68, 83.68, 79.91, 79.77, 109.96],
             'y': [8131.34, 6244.66, 5923.22, 1856.36, 1493.0]},
            {'name': 'MORB+IAT+CAB',
             'position': [60, 5500],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [83.68, 79.91, 43.71, 35.89, 47.76, 69.57],
             'y': [6244.66, 5923.22, 3044.28, 3812.93, 5923.22, 7628.23]},
            {'name': 'IAT',
             'position': [22, 2700],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [79.91, 79.77, 4.16, 18.28, 59.08, 69.57, 47.76, 35.89, 43.71, 79.91, 83.68],
             'y': [5923.22, 1856.36, 1618.78, 4330.02, 8634.46, 7628.23, 5923.22, 3812.93, 3044.28, 5923.22, 6244.66]},
        ]

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        zr = get_element_value(feature, layer, 'Zr')
        ti = get_element_value(feature, layer, 'Ti')
        if zr is not None and ti is not None and zr > 0 and ti > 0:
            return zr, ti
        return None, None

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None, sample_sizes=None):
        cls.draw_fields(ax)

        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter, category_artists = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors,
                                          sample_sizes=sample_sizes)

        ax.set_xlabel('Zr (ppm)', fontsize=12)
        ax.set_ylabel('Ti (ppm)', fontsize=12)
        n_str = f' (n={n_samples})' if n_samples is not None else ''
        ax.set_title(f'{cls.name}{n_str}\n{cls.reference}', fontsize=11)
        ax.set_xlim(0, 110)
        ax.set_ylim(0, 9000)

        if show_category_legend and category_colors and len(category_colors) > 0:
            n_categories = len(category_colors)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=8,
                     ncol=ncol, framealpha=0.9, borderaxespad=0.)

        if show_legend:
            legend_text = "IAT = Island arc tholeiites\nMORB = Mid-ocean ridge basalts\nCAB = Calc-alkaline basalts"
            ax.text(0.02, 0.98, legend_text, transform=ax.transAxes, fontsize=8,
                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        return fid_to_scatter, category_artists


class Wilson1989_TAS(PolygonDiagramMixin):
    """Na2O + K2O vs SiO2 Cox et al. (1979) adapted by Wilson (1989) for plutonic rocks"""

    name = "Na2O + K2O vs SiO2"
    reference = "Wilson (1989) Plutonic Rocks"
    field_name = "Wilsn89TAS"
    
    @classmethod
    def _get_fields(cls):
        """Return field polygon definitions as a list of dicts with label attributes and open polygon vertices."""
        return [
            {
                'name': 'Ijolite',
                'position': [39.0, 7.0],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [40.02, 42.91, 38.68, 35.29, 35.29,40.02],
                'y': [9.52, 8.41, 4.22, 6.29, 6.72, 9.52]
            },
            {
                'name': 'void',
                'position': [45.5, 11.6],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [48.21, 50.78, 44.93, 42.91, 40.02, 48.21],
                'y': [15.0, 13.4, 9.63, 8.41, 9.52, 15.0]
            },
            {
                'name': 'Nepheline-Syenite',
                'position': [54.6, 14.0],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [48.21, 51.16, 51.83, 61.44, 57.23, 54.14, 50.78],
                'y': [15.0, 16.8, 16.81, 14.11, 11.42, 11.32, 13.4]
            },
            {
                'name': 'void',
                'position': [49.6, 10.9],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [50.78, 54.14, 49.24, 47.54, 44.93],
                'y': [13.4, 11.32, 9.32, 8.61, 9.63]
            },
            {
                'name': 'void',
                'position': [43.0, 6.6],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [44.93, 47.54, 45.56, 43.99, 40.71, 38.68, 42.91, 44.93, 47.54],
                'y': [9.63, 8.61, 7.15, 5.94, 3.25, 4.22, 8.41, 9.63, 8.61]
            },
            {
                'name': 'Gabbro',
                'position': [46.8, 3.8],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [40.71, 43.99, 51.52, 51.39, 51.33, 43.67, 40.71],
                'y': [3.25, 5.94, 5.71, 5.16, 1.66, 1.95, 3.25]
            },
            {
                'name': 'Gabbro',
                'position': [48.5, 6.5],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [43.99, 45.56, 52.3, 51.52],
                'y': [5.94, 7.15, 7.21, 5.71]
            },
            {
                'name': 'Syenodiorite',
                'position': [50.6, 8.2],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [49.24, 55.95, 52.3, 45.56, 47.54],
                'y': [9.32, 9.16, 7.21, 7.15, 8.61]
            },
            {
                'name': 'Syenite',
                'position': [55.3, 10.2],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [49.24, 54.14, 57.23, 61.07, 55.95],
                'y': [9.32, 11.32, 11.42, 10.06, 9.16]
            },
            {
                'name': 'Syenite',
                'position': [63.0, 11.5],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [61.44, 68.74, 64.47, 61.07, 57.23],
                'y': [14.11, 11.8, 8.85, 10.06, 11.42]
            },
            {
                'name': 'Syenodiorite',
                'position': [58.1, 7.8],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [51.52, 52.3, 55.95, 61.07, 64.47, 62.45, 54.39],
                'y': [5.71, 7.21, 9.16, 10.06, 8.85, 6.92, 5.69]
            },
            {
                'name': 'Gabbro-Diorite',
                'position': [52.9, 3.7],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [51.52, 54.39, 54.57, 51.33, 51.39],
                'y': [5.71, 5.69, 1.75, 1.66, 5.16]
            },
            {
                'name': 'Diorite',
                'position': [58.4, 4.5],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [54.39, 62.45, 62.53, 54.57],
                'y': [5.69, 6.92, 3.53, 1.75]
            },
            {
                'name': 'Granodiorite',
                'position': [65.2, 6.1],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [62.45, 64.47, 66.28, 69.58, 62.53],
                'y': [6.92, 8.85, 8.03, 5.55, 3.53]
            },
            {
                'name': 'Granite',
                'position': [70.0, 8.7],
                'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
                'rotation': 0, 'color': 'k',
                'x': [64.47, 68.74, 73.72, 74.76, 74.86, 73.96, 69.58, 66.28],
                'y': [8.85, 11.8, 9.72, 8.93, 7.92, 7.15, 5.55, 8.03]
            },
        ]

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        na = get_element_value(feature, layer, 'Na2O')
        k = get_element_value(feature, layer, 'K2O')
        si = get_element_value(feature, layer, 'SiO2')

        if na is not None and k is not None and si is not None and na > 0 and k > 0 and si > 0:
            return si, (na + k)
        return None, None

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None, sample_sizes=None):
        cls.draw_fields(ax)

        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter, category_artists = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors,
                                          sample_sizes=sample_sizes)

        ax.plot([43.7, 46.9, 51.4, 53.1, 58.5, 63.3, 66.3, 71.2, 74.7],
                [1.9, 3.4, 5.2, 5.7, 7.0, 7.7, 8.0, 8.3, 8.4], 'g--', linewidth=1.)  
        ax.text(58.3, 7.3, 'Alkaline', fontsize=10, ha='center', va='center', rotation=20, color='g')
        ax.text(58.6, 6.6, 'Sub-alkaline', fontsize=10, ha='center', va='center', rotation=20, color='g')    
        ax.set_xlabel('SiO2 (wt%)', fontsize=12)
        ax.set_ylabel('Na2O + K2O (wt%)', fontsize=12)
        n_str = f' (n={n_samples})' if n_samples is not None else ''
        ax.set_title(f'{cls.name}{n_str}\n{cls.reference}', fontsize=11)
        ax.set_xlim(30, 80)
        ax.set_ylim(0, 17)
        
        if show_category_legend and category_colors and len(category_colors) > 0:
            n_categories = len(category_colors)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=8,
                     ncol=ncol, framealpha=0.9, borderaxespad=0.)
        return fid_to_scatter, category_artists


class Cox1979_TAS(PolygonDiagramMixin):
    """Na2O + K2O vs SiO2 Cox et al. (1979) for volcanic rocks"""

    name = "Na2O + K2O vs SiO2"
    reference = "Cox et al. (1979) Volcanic Rocks"
    field_name = "Cox79_TAS"
    # AKA Le Bas, 1986

    @classmethod
    def _get_fields(cls):
        """Return field polygon definitions with label attributes and open polygon vertices."""
        return [
            {'name': 'Foidite',
             'position': [43, 13],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [41.0, 52.5, 49.0],
             'y': [7.0, 14.0, 15.5]},
            {'name': 'Picro-basalt',
             'position': [43, 2],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [45, 45, 41, 41],
             'y': [0, 3, 3, 0]},
            {'name': 'Basalt',
             'position': [48, 3],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [52, 52, 45, 45],
             'y': [0, 5, 5, 0]},
            {'name': 'Basaltic Andesite',
             'position': [54.8, 3.5],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [57, 57, 52, 52],
             'y': [0, 5.9, 5, 0]},
            {'name': 'Andesite',
             'position': [60, 4],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [63, 63, 57, 57],
             'y': [0, 7, 5.9, 0]},
            {'name': 'Dacite',
             'position': [67, 4.5],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [77, 69, 63, 63],
             'y': [0, 8, 7, 0]},
            {'name': 'Rhyolite',
             'position': [73, 11],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [80, 80, 77, 69, 69],
             'y': [13, 0, 0, 8, 13]},
            {'name': 'Tephrite-Basanite',
             'position': [43, 5.75],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [45, 45, 49.4, 45, 41, 41],
             'y': [3, 5, 7.3, 9.4, 7, 3]},
            {'name': 'Trachy-basalt',
             'position': [48.8, 5.75],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [52, 49.4, 45],
             'y': [5, 7.3, 5]},
            {'name': 'Basaltic trachy-andesite',
             'position': [52.7, 7],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [52, 57, 53, 49.4],
             'y': [5, 5.9, 9.3, 7.3]},
            {'name': 'Trachy-andesite',
             'position': [58, 8],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [57, 63, 57.6, 53],
             'y': [5.9, 7, 11.7, 9.3]},
            {'name': 'Trachyte-Trachydacite',
             'position': [65, 10],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [63, 57.6, 63, 69, 69],
             'y': [14.56, 11.7, 7, 8, 13]},
            {'name': 'Phono-tephrite',
             'position': [48, 9.5],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [49.4, 53, 48.4, 45],
             'y': [7.3, 9.3, 11.5, 9.4]},
            {'name': 'Tephri-phonolite',
             'position': [53, 12],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [53, 57.6, 52.5, 48.4],
             'y': [9.3, 11.7, 14, 11.5]},
            {'name': 'Phonolite',
             'position': [56.5, 14],
             'fontsize': 12, 'ha': 'center', 'va': 'center', 'fontweight': 'normal',
             'rotation': 0, 'color': 'k',
             'x': [63, 57.6, 52.5, 49],
             'y': [14.56, 11.7, 14, 15.5]},
        ]

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        na = get_element_value(feature, layer, 'Na2O')
        k = get_element_value(feature, layer, 'K2O')
        si = get_element_value(feature, layer, 'SiO2')

        if na is not None and k is not None and si is not None and na > 0 and k > 0 and si > 0:
            return si, (na + k)
        return None, None

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None, sample_sizes=None):
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter, category_artists = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors,
                                          sample_sizes=sample_sizes)
        
        ax.set_xlabel('SiO2 (wt%)', fontsize=12)
        ax.set_ylabel('Na2O + K2O (wt%)', fontsize=12)
        n_str = f' (n={n_samples})' if n_samples is not None else ''
        ax.set_title(f'{cls.name}{n_str}\n{cls.reference}', fontsize=11)
        ax.set_xlim(40, 80)
        ax.set_ylim(0, 17)
        
        if show_category_legend and category_colors and len(category_colors) > 0:
            n_categories = len(category_colors)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=8,
                     ncol=ncol, framealpha=0.9, borderaxespad=0.)
        return fid_to_scatter, category_artists


class ApatiteGroupPlot(PolygonDiagramMixin):
    """Sr/Y vs Sum(La+Ce+Pr+Nd) apatite group classification diagram."""

    name = "Σ(La+Ce+Pr+Nd) vs Sr/Y"
    reference = "Apatite Group Classification"
    field_name = "Ap_Class"

    @classmethod
    def _get_fields(cls):
        return [
            {'name': 'LM',
             'position': [20, 100],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'bold',
             'rotation': 0, 'color': 'k',
             'x': [0.1, 0.1, 1173.095404, 1037.528416, 987.7946432, 940.4448517,
                   895.3647655, 852.4455867, 811.5837324, 772.6805851, 895.3647655,
                   772.6805851, 811.5837324, 873.6416559, 963.8290236, 963.8290236,
                   987.7946432, 1012.356168, 1012.356168, 1063.326572, 1116.863248,
                   1173.095404, 1232.158753, 1326.376036, 1393.156803, 1575.191405,
                   1825.296131, 1870.68214, 1825.296131, 1737.800829, 1614.358557,
                   1463.299868, 1359.356391, 1262.796395, 1232.158753, 1202.264435,
                   1232.158753, 1262.796395, 1294.195841, 1232.158753, 1144.634065,
                   1063.326572, 987.7946432, 895.3647655, 811.5837324, 753.9340075,
                   717.7942913, 683.3869271, 650.6288749, 634.8434844, 634.8434844, 0.1],
             'y': [1000, 0.001, 0.001, 0.005096793, 0.005827974, 0.007007391,
                   0.008712456, 0.010652514, 0.013244524, 0.016745315, 0.017603343,
                   0.021169545, 0.027671733, 0.036780239, 0.054964518, 0.062844061,
                   0.078125049, 0.10042962, 0.12074296, 0.150095781, 0.189735187,
                   0.252200216, 0.335230118, 0.430899269, 0.535651622, 0.761224447,
                   0.89975369, 1.011610511, 1.176216514, 1.462417971, 1.78814373,
                   2.377477216, 3.214279484, 4.064058961, 5.313039324, 6.605533186,
                   8.211716348, 9.708269375, 11.09952113, 12.6918476, 15.51871501,
                   19.62149623, 24.80895577, 31.89899274, 42.41221058, 52.73446513,
                   63.40643463, 81.51978588, 113.9610294, 148.9839189, 1000, 1000]},
            {'name': 'S',
             'position': [8000, 0.005],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'bold',
             'rotation': 0, 'color': 'k',
             'x': [1173.095404, 1037.528416, 987.7946432, 940.4448517, 895.3647655,
                   852.4455867, 811.5837324, 772.6805851, 895.3647655, 1089.766199,
                   1393.156803, 1781.011266, 2221.604092, 2703.958364, 3456.739614,
                   4641.588834, 5789.841391, 7585.77575, 10185.91388, 12705.74105,
                   17060.82389, 20765.06684, 22908.67653, 25902.00205, 28575.90543,
                   32309.73034, 35645.11334, 37439.7839, 39324.81305, 40302.62497,
                   40302.62497, 39324.81305, 38370.72455, 37439.7839, 1173.095404],
             'y': [0.001, 0.005096793, 0.005827974, 0.007007391, 0.008712456,
                   0.010652514, 0.013244524, 0.016745315, 0.017603343, 0.019133906,
                   0.021867116, 0.025412777, 0.02953467, 0.033756607, 0.039230098,
                   0.047935735, 0.0557108, 0.06694622, 0.081802403, 0.076471676,
                   0.069124422, 0.064622753, 0.055571655, 0.044690057, 0.036547747,
                   0.027951171, 0.021738597, 0.017193906, 0.013599332, 0.010756723,
                   0.008228418, 0.006190125, 0.004656745, 0.001, 0.001]},
            {'name': 'HM',
             'position': [3000, 0.07],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'bold',
             'rotation': 0, 'color': 'k',
             'x': [1825.296131, 1575.191405, 1393.156803, 1326.376036, 1232.158753,
                   1173.095404, 1116.863248, 1063.326572, 1012.356168, 1012.356168,
                   987.7946432, 963.8290236, 963.8290236, 873.6416559, 811.5837324,
                   772.6805851, 895.3647655, 1089.766199, 1393.156803, 1781.011266,
                   2221.604092, 2703.958364, 3456.739614, 4641.588834, 5789.841391,
                   7585.77575, 10185.91388, 9008.794217, 8165.823714, 6875.95987,
                   5933.805863, 4996.508915, 4207.266284, 3542.691484, 2910.717118,
                   2511.886432, 2063.795526, 1825.296131],
             'y': [0.89975369, 0.761224447, 0.535651622, 0.430899269, 0.335230118,
                   0.252200216, 0.189735187, 0.150095781, 0.12074296, 0.10042962,
                   0.078125049, 0.062844061, 0.054964518, 0.036780239, 0.027671733,
                   0.021169545, 0.017603343, 0.019133906, 0.021867116, 0.025412777,
                   0.02953467, 0.033756607, 0.039230098, 0.047935735, 0.0557108,
                   0.06694622, 0.081802403, 0.088966533, 0.101738671, 0.133040986,
                   0.159993308, 0.209219043, 0.273590244, 0.351825467, 0.460093461,
                   0.591634285, 0.773699153, 0.89975369]},
            {'name': 'IM',
             'position': [8000, 2],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'bold',
             'rotation': 0, 'color': 'k',
             'x': [1294.195841, 1262.796395, 1232.158753, 1202.264435, 1232.158753,
                   1262.796395, 1359.356391, 1463.299868, 1614.358557, 1737.800829,
                   1825.296131, 1870.68214, 1825.296131, 2063.795526, 2511.886432,
                   2910.717118, 3542.691484, 4207.266284, 4996.508915, 5933.805863,
                   6875.95987, 8165.823714, 9008.794217, 10185.91388, 12705.74105,
                   17060.82389, 20765.06684, 24062.08925, 23478.30103, 22908.67653,
                   22352.87211, 22908.67653, 23478.30103, 24062.08925, 24660.39337,
                   25902.00205, 26546.05562, 27882.60417, 27882.60417, 28575.90543,
                   27882.60417, 27206.12359, 25273.57433, 23478.30103, 20765.06684,
                   18365.38343, 15848.93192, 13677.28826, 11803.20636, 9938.785858,
                   7774.39615, 6081.350013, 4641.588834, 3372.873087, 2391.479523,
                   1825.296131, 1294.195841],
             'y': [11.09952113, 9.708269375, 8.211716348, 6.605533186, 5.313039324,
                   4.064058961, 3.214279484, 2.377477216, 1.78814373, 1.462417971,
                   1.176216514, 1.011610511, 0.89975369, 0.773699153, 0.591634285,
                   0.460093461, 0.351825467, 0.273590244, 0.209219043, 0.159993308,
                   0.133040986, 0.101738671, 0.088966533, 0.081802403, 0.076471676,
                   0.069124422, 0.064622753, 0.061439958, 0.078988017, 0.101548033,
                   0.137277702, 0.179450322, 0.226852218, 0.268195143, 0.317072654,
                   0.400809662, 0.48999485, 0.629859431, 0.757257592, 0.95728758,
                   1.131850562, 1.383825127, 1.663946636, 2.06891682, 2.660301805,
                   3.30805966, 4.183192776, 5.030651615, 6.151957596, 6.691334291,
                   7.654000475, 8.466789994, 9.210766178, 9.854595167, 10.3687997,
                   10.72722211, 11.09952113]},
            {'name': 'UM',
             'position': [20000, 40],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'bold',
             'rotation': 0, 'color': 'k',
             'x': [634.8434844, 634.8434844, 650.6288749, 683.3869271, 717.7942913,
                   753.9340075, 811.5837324, 895.3647655, 987.7946432, 1063.326572,
                   1144.634065, 1232.158753, 1294.195841, 1825.296131, 2391.479523,
                   3372.873087, 4641.588834, 6081.350013, 7774.39615, 9938.785858,
                   12096.69322, 14017.37418, 16243.0158, 18822.0389, 22352.87211,
                   27206.12359, 32309.73034, 37439.7839, 44463.12675, 59703.52866,
                   74473.19739, 86297.85478, 92896.63868, 100000, 105034.8291,
                   107646.5214, 110323.1533, 110323.1533, 110323.1533, 110323.1533,
                   634.8434844],
             'y': [1000, 148.9839189, 113.9610294, 81.51978588, 63.40643463,
                   52.73446513, 42.41221058, 31.89899274, 24.80895577, 19.62149623,
                   15.51871501, 12.6918476, 11.09952113, 10.72722211, 10.3687997,
                   9.854595167, 9.210766178, 8.466789994, 7.654000475, 6.691334291,
                   8.599010611, 9.995089025, 11.61782548, 13.05923015, 14.19532874,
                   15.69013451, 17.05511081, 17.92901224, 18.8468506, 21.53713244,
                   25.03040512, 30.59315326, 36.16540503, 44.95526955, 54.95592795,
                   67.18431272, 92.34859725, 114.8089533, 142.7319543, 1000, 1000]},
            {'name': 'ALK',
             'position': [200000, 3],
             'fontsize': 11, 'ha': 'center', 'va': 'center', 'fontweight': 'bold',
             'rotation': 0, 'color': 'k',
             'x': [110323.1533, 110323.1533, 110323.1533, 110323.1533, 107646.5214,
                   105034.8291, 100000, 92896.63868, 86297.85478, 74473.19739,
                   59703.52866, 44463.12675, 37439.7839, 32309.73034, 27206.12359,
                   22352.87211, 18822.0389, 16243.0158, 14017.37418, 12096.69322,
                   9938.785858, 11803.20636, 13677.28826, 15848.93192, 18365.38343,
                   20765.06684, 23478.30103, 25273.57433, 27206.12359, 27882.60417,
                   28575.90543, 27882.60417, 27882.60417, 26546.05562, 25902.00205,
                   24660.39337, 24062.08925, 23478.30103, 22908.67653, 22352.87211,
                   22908.67653, 23478.30103, 24062.08925, 20765.06684, 22908.67653,
                   25902.00205, 28575.90543, 32309.73034, 35645.11334, 37439.7839,
                   39324.81305, 40302.62497, 40302.62497, 39324.81305, 38370.72455,
                   37439.7839, 1000000, 1000000, 110323.1533],
             'y': [1000, 142.7319543, 114.8089533, 92.34859725, 67.18431272,
                   54.95592795, 44.95526955, 36.16540503, 30.59315326, 25.03040512,
                   21.53713244, 18.8468506, 17.92901224, 17.05511081, 15.69013451,
                   14.19532874, 13.05923015, 11.61782548, 9.995089025, 8.599010611,
                   6.691334291, 6.151957596, 5.030651615, 4.183192776, 3.30805966,
                   2.660301805, 2.06891682, 1.663946636, 1.383825127, 1.131850562,
                   0.95728758, 0.757257592, 0.629859431, 0.48999485, 0.400809662,
                   0.317072654, 0.268195143, 0.226852218, 0.179450322, 0.137277702,
                   0.101548033, 0.078988017, 0.061439958, 0.064622753, 0.055571655,
                   0.044690057, 0.036547747, 0.027951171, 0.021738597, 0.017193906,
                   0.013599332, 0.010756723, 0.008228418, 0.006190125, 0.004656745,
                   0.001, 0.001, 1000, 1000]},
        ]

    @classmethod
    def classify_point(cls, x, y):
        import math
        if x is None or y is None or x <= 0 or y <= 0:
            return None
        lx, ly = math.log10(x), math.log10(y)
        for f in cls._get_fields():
            log_xs = [math.log10(v) for v in f['x']] + [math.log10(f['x'][0])]
            log_ys = [math.log10(v) for v in f['y']] + [math.log10(f['y'][0])]
            if Path(list(zip(log_xs, log_ys))).contains_point((lx, ly)):
                name = f['name']
                return name if name != 'void' else ''
        return None

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        la = get_element_value(feature, layer, 'La')
        ce = get_element_value(feature, layer, 'Ce')
        pr = get_element_value(feature, layer, 'Pr')
        nd = get_element_value(feature, layer, 'Nd')
        sr = get_element_value(feature, layer, 'Sr')
        y_elem = get_element_value(feature, layer, 'Y')

        lree_vals = [v for v in [la, ce, pr, nd] if v is not None and v > 0]
        if not lree_vals:
            return None, None
        sum_lree = sum(lree_vals)

        if sr is None or y_elem is None or y_elem <= 0 or sr <= 0:
            return None, None
        return sum_lree, sr / y_elem

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True,
             sample_colors=None, category_colors=None, sample_markers=None,
             category_markers=None, n_samples=None, fids=None, sample_sizes=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)

        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter, category_artists = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors,
                                          sample_sizes=sample_sizes)

        ax.set_xlabel('Σ(La+Ce+Pr+Nd) (ppm)', fontsize=12)
        ax.set_ylabel('Sr/Y', fontsize=12)
        n_str = f' (n={n_samples})' if n_samples is not None else ''
        ax.set_title(f'{cls.name}{n_str}\n{cls.reference}', fontsize=11)
        ax.set_xlim(0.1, 1e6)
        ax.set_ylim(0.001, 1000)

        if show_category_legend and category_colors and len(category_colors) > 0:
            n_categories = len(category_colors)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=8,
                      ncol=ncol, framealpha=0.9, borderaxespad=0.)
        return fid_to_scatter, category_artists


DISCRIMINATION_DIAGRAMS = {
    'Na2O + K2O vs SiO2 Plutonic (Wilson 1989)': Wilson1989_TAS,
    'Na2O + K2O vs SiO2 Volcanic (Cox et al 1979)': Cox1979_TAS,
    'Zr/Ti vs Nb/Y (Pearce 1996)': Pearce1996_NbY_ZrTi,
    'Zr/Ti vs Nb/Y (Winchester & Floyd 1977)': Winchester_Floyd1977_NbY_ZrTi,
    'Zr/4-Nb×2-Y Ternary (Meschede 1986)': Meschede1986_Ternary,
    'Nb vs Y (Pearce et al. 1984)': Pearce1984_YNb,
    'Rb vs (Y+Nb) (Pearce et al. 1984)': Pearce1984_YNbRb,
    'Ti vs Zr (Pearce & Cann 1973)': PearceCann1973_ZrTi
}

# Mineral classification plots, shown in the Minerals tab's plot-type dropdown.
# Currently a single entry; more classification schemes can be added here
# without any other code changes.
MINERALS_DIAGRAMS = {
    'Detrital Apatite Classification (Sullivan, 2020)': ApatiteGroupPlot,
}


# =============================================================================
# DOCK WIDGET CLASS
# =============================================================================

class GeochemistryDockWidget(QDockWidget):
    """Dockable widget for geochemistry plotting tools."""
    
    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        super().__init__("Geochemistry Plotting Tools", parent)
        self.iface = iface
        self.current_fig = None
        self._category_controls = None
        self.setAllowedAreas(LeftDockWidgetArea | RightDockWidgetArea)
        self.setup_ui()
        self.load_layers()

        # Connect to layer registry for updates
        QgsProject.instance().layersAdded.connect(self.load_layers)
        QgsProject.instance().layersRemoved.connect(self.load_layers)

    def closeEvent(self, event):
        """Handle close event."""
        self.closingPlugin.emit()
        event.accept()

    def _label_row(self, label_text, *controls, spacing=20, trailing_stretch=False, expand_index=-1):
        """Build a QHBoxLayout: a label sized to its own text, a fixed
        `spacing`-px gap, then `controls` in order.

        The control at `expand_index` (default: the last one) is given an
        Expanding size policy and all the layout stretch, so it grows to
        fill the row's remaining width instead of leaving a gap between it
        and the label, or leaving it stranded away from the label. Other
        controls keep their natural content-sized width. Pass
        `trailing_stretch=True` instead for rows of same-sized controls
        (e.g. checkboxes) that should hug the label with unused space left
        at the row's right edge.
        """
        row = QHBoxLayout()
        row.setSpacing(spacing)
        label = QLabel(label_text)
        label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        row.addWidget(label, 0)
        if expand_index < 0:
            expand_index = len(controls) + expand_index
        for i, control in enumerate(controls):
            if not trailing_stretch and i == expand_index:
                control.setSizePolicy(QSizePolicy_Expanding, QSizePolicy_Fixed)
                row.addWidget(control, 1)
            else:
                control.setSizePolicy(QSizePolicy_Minimum, QSizePolicy_Fixed)
                row.addWidget(control, 0)
        if trailing_stretch:
            row.addStretch()
        return row

    def _checkbox_row(self, *checkboxes, spacing=12):
        """Build a QHBoxLayout that packs `checkboxes` tightly on the left
        (each already carries its own text as a label), leaving unused
        space at the row's right edge instead of spreading them out."""
        row = QHBoxLayout()
        row.setSpacing(spacing)
        for checkbox in checkboxes:
            checkbox.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
            row.addWidget(checkbox, 0)
        row.addStretch()
        return row

    def _create_bubble_size_group(self, prefix, field_items, editable=False):
        """Build a reusable 'Bubble Size (optional)' control group.

        Widgets are stored as self.<prefix>_bubble_field_combo,
        self.<prefix>_bubble_scale_combo, self.<prefix>_bubble_min_size_spin,
        self.<prefix>_bubble_max_size_spin and self.<prefix>_bubble_range_label,
        so each plot tab keeps an independent set of bubble-size controls.
        Returns the QGroupBox to add to the tab's layout.
        """
        group = QGroupBox("Bubble Size (optional)")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(3)

        size_by_label = QLabel("Size by:")
        size_by_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        grid.addWidget(size_by_label, 0, 0)
        field_combo = QComboBox()
        field_combo.addItems(field_items)
        field_combo.setEditable(editable)
        field_combo.setSizePolicy(QSizePolicy_Expanding, QSizePolicy_Fixed)
        if editable:
            field_combo.setToolTip("Pick a field, or type an exact layer field name.")
        grid.addWidget(field_combo, 0, 1, 1, 3)
        setattr(self, f'{prefix}_bubble_field_combo', field_combo)

        scaling_label = QLabel("Scaling:")
        scaling_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        grid.addWidget(scaling_label, 1, 0)
        scale_combo = QComboBox()
        scale_combo.addItems(["Linear", "Log10", "Exponential"])
        scale_combo.setSizePolicy(QSizePolicy_Expanding, QSizePolicy_Fixed)
        grid.addWidget(scale_combo, 1, 1, 1, 3)
        setattr(self, f'{prefix}_bubble_scale_combo', scale_combo)

        min_label = QLabel("Min size:")
        min_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        grid.addWidget(min_label, 2, 0)
        min_spin = QDoubleSpinBox()
        min_spin.setRange(1.0, 5000.0)
        min_spin.setDecimals(0)
        min_spin.setSingleStep(10.0)
        min_spin.setValue(20.0)
        min_spin.setToolTip("Symbol area (pt²) for the smallest value in the data.")
        grid.addWidget(min_spin, 2, 1)
        setattr(self, f'{prefix}_bubble_min_size_spin', min_spin)

        max_label = QLabel("Max size:")
        max_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        grid.addWidget(max_label, 2, 2)
        max_spin = QDoubleSpinBox()
        max_spin.setRange(1.0, 5000.0)
        max_spin.setDecimals(0)
        max_spin.setSingleStep(10.0)
        max_spin.setValue(400.0)
        max_spin.setToolTip("Symbol area (pt²) for the largest value in the data.")
        grid.addWidget(max_spin, 2, 3)
        setattr(self, f'{prefix}_bubble_max_size_spin', max_spin)

        range_label = QLabel("Data range: (select a field to enable bubble sizing)")
        range_label.setWordWrap(True)
        range_label.setStyleSheet("color: gray; font-style: italic;")
        grid.addWidget(range_label, 3, 0, 1, 4)
        setattr(self, f'{prefix}_bubble_range_label', range_label)

        return group

    def _read_bubble_controls(self, prefix):
        """Return (size_field, bubble_active, min_size, max_size, method) for a
        tab's bubble-size controls created by _create_bubble_size_group()."""
        size_field = getattr(self, f'{prefix}_bubble_field_combo').currentText().strip()
        bubble_active = bool(size_field) and size_field != '1 (none)'
        min_size = getattr(self, f'{prefix}_bubble_min_size_spin').value()
        max_size = getattr(self, f'{prefix}_bubble_max_size_spin').value()
        method = BUBBLE_SCALE_METHODS.get(getattr(self, f'{prefix}_bubble_scale_combo').currentText(), 'linear')
        return size_field, bubble_active, min_size, max_size, method

    def _compute_bubble_range(self, prefix, size_data, valid_mask, method):
        """Compute (vmin, vmax) from size_data at positions where valid_mask is
        True, update the tab's range label, and return (vmin, vmax, active)."""
        range_label = getattr(self, f'{prefix}_bubble_range_label')
        values = [v for v, valid in zip(size_data, valid_mask)
                 if valid and v is not None and (method != 'log10' or v > 0)]
        if not values:
            range_label.setText("Data range: (no usable values for the selected field)")
            range_label.setStyleSheet("color: gray; font-style: italic;")
            return None, None, False
        vmin, vmax = min(values), max(values)
        min_size = getattr(self, f'{prefix}_bubble_min_size_spin').value()
        max_size = getattr(self, f'{prefix}_bubble_max_size_spin').value()
        method_label = getattr(self, f'{prefix}_bubble_scale_combo').currentText()
        range_label.setText(
            f"Data range: {vmin:.4g} – {vmax:.4g}  →  size {min_size:.0f} – {max_size:.0f} pt² ({method_label})")
        range_label.setStyleSheet("color: black;")
        return vmin, vmax, True

    def _resize_tab_widget_to_current(self, index, tab_widget=None):
        """Shrink `tab_widget` (self.tab_widget by default) to the height of
        its currently visible tab.

        QTabWidget otherwise sizes itself to fit the tallest tab, so every
        other (shorter) tab shows a block of empty space below its content.
        Giving hidden pages an Ignored size policy excludes them from the
        stacked widget's size hint, leaving only the current page's height.
        """
        tab_widget = tab_widget or self.tab_widget
        for i in range(tab_widget.count()):
            page = tab_widget.widget(i)
            if page is None:
                continue
            if i == index:
                page.setSizePolicy(QSizePolicy_Preferred, QSizePolicy_Preferred)
            else:
                page.setSizePolicy(QSizePolicy_Ignored, QSizePolicy_Ignored)
        tab_widget.adjustSize()

    def setup_ui(self):
        """Setup the user interface."""
        # Main widget with scroll area
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Layer selection
        layer_group = QGroupBox("Layer Selection")
        layer_layout = QVBoxLayout(layer_group)
        layer_layout.setSpacing(3)

        self.layer_combo = QComboBox()
        self.layer_combo.currentIndexChanged.connect(self.on_layer_changed)
        layer_layout.addLayout(self._label_row("Layer:", self.layer_combo))

        self.id_field_combo = QComboBox()
        self.id_field_combo.currentIndexChanged.connect(self.on_id_field_changed)
        layer_layout.addLayout(self._label_row("Category:", self.id_field_combo))

        self.label_field_combo = QComboBox()
        self.discrim_label = QCheckBox()
        self.discrim_label.setChecked(False)
        self.discrim_label.setToolTip("Label selected points using this field")
        layer_layout.addLayout(
            self._label_row("Add label:", self.label_field_combo, self.discrim_label, expand_index=0))

        main_layout.addWidget(layer_group)

        style_hint = QLabel(
            "Category colours, markers and visibility can be edited from the "
            "“Style…” panel that opens alongside each generated plot."
        )
        style_hint.setWordWrap(True)
        style_hint.setStyleSheet("color: gray; font-style: italic;")
        main_layout.addWidget(style_hint)

        # Tabs
        self.tab_widget = QTabWidget()

        # Tab 1: Spider Diagram
        spider_tab = QWidget()
        spider_layout = QVBoxLayout(spider_tab)
        spider_layout.setSpacing(5)

        self.norm_combo = QComboBox()
        for norm_name, norm_values in NORMALIZATION_OPTIONS:
            self.norm_combo.addItem(norm_name, norm_values)
        spider_layout.addLayout(self._label_row("Normalize:", self.norm_combo))

        self.order_combo = QComboBox()
        self.order_combo.addItems(["REE Only (La-Lu)", "Extended (Ba-Yb)", "Extended Alt (Cs-Lu)"])
        spider_layout.addLayout(self._label_row("Elements:", self.order_combo))

        self.spider_legend = QCheckBox("Legend")
        self.spider_legend.setChecked(True)
        self.spider_markers = QCheckBox("Markers")
        self.spider_markers.setChecked(True)
        spider_layout.addLayout(self._checkbox_row(self.spider_legend, self.spider_markers))

        spider_layout.addWidget(self._create_bubble_size_group('spider', CUSTOM_XY_ELEMENTS, editable=True))
        spider_layout.addStretch()

        self.tab_widget.addTab(spider_tab, "Spider")

        # Tab 2: Discrimination Diagrams
        discrim_tab = QWidget()
        discrim_layout = QVBoxLayout(discrim_tab)
        discrim_layout.setSpacing(5)

        self.diagram_combo = QComboBox()
        self.diagram_combo.addItems(list(DISCRIMINATION_DIAGRAMS.keys()))
        discrim_layout.addWidget(self.diagram_combo)

        self.discrim_legend = QCheckBox("Field Legend")
        self.discrim_legend.setChecked(True)
        self.discrim_category_legend = QCheckBox("Category Legend")
        self.discrim_category_legend.setChecked(True)
        discrim_layout.addLayout(self._checkbox_row(self.discrim_legend, self.discrim_category_legend))

        discrim_layout.addWidget(self._create_bubble_size_group('discrim', CUSTOM_XY_ELEMENTS, editable=True))
        discrim_layout.addStretch()

        self.tab_widget.addTab(discrim_tab, "Discrimination/Classification")

        # Tab 3: Custom XY Plot
        custom_xy_tab = QWidget()
        custom_xy_outer_layout = QVBoxLayout(custom_xy_tab)
        custom_xy_outer_layout.setContentsMargins(0, 0, 0, 0)
        custom_xy_subtabs = QTabWidget()

        plot_setup_tab = QWidget()
        custom_xy_layout = QVBoxLayout(plot_setup_tab)
        custom_xy_layout.setSpacing(5)

        # X-axis
        x_group = QGroupBox("X-Axis")
        x_grid = QGridLayout(x_group)
        x_grid.setHorizontalSpacing(20)
        x_grid.setVerticalSpacing(3)
        x_num_label = QLabel("Num:")
        x_num_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        x_grid.addWidget(x_num_label, 0, 0)
        self.x_num_combo = QComboBox()
        self.x_num_combo.addItems(CUSTOM_XY_ELEMENTS[1:])
        self.x_num_combo.setSizePolicy(QSizePolicy_Minimum, QSizePolicy_Fixed)
        x_grid.addWidget(self.x_num_combo, 0, 1)
        x_denom_label = QLabel("Denom:")
        x_denom_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        x_grid.addWidget(x_denom_label, 0, 2)
        self.x_denom_combo = QComboBox()
        self.x_denom_combo.addItems(CUSTOM_XY_ELEMENTS)
        self.x_denom_combo.setSizePolicy(QSizePolicy_Expanding, QSizePolicy_Fixed)
        x_grid.addWidget(self.x_denom_combo, 0, 3)
        custom_xy_layout.addWidget(x_group)

        # Y-axis
        y_group = QGroupBox("Y-Axis")
        y_grid = QGridLayout(y_group)
        y_grid.setHorizontalSpacing(20)
        y_grid.setVerticalSpacing(3)
        y_num_label = QLabel("Num:")
        y_num_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        y_grid.addWidget(y_num_label, 0, 0)
        self.y_num_combo = QComboBox()
        self.y_num_combo.addItems(CUSTOM_XY_ELEMENTS[1:])
        self.y_num_combo.setSizePolicy(QSizePolicy_Minimum, QSizePolicy_Fixed)
        y_grid.addWidget(self.y_num_combo, 0, 1)
        y_denom_label = QLabel("Denom:")
        y_denom_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        y_grid.addWidget(y_denom_label, 0, 2)
        self.y_denom_combo = QComboBox()
        self.y_denom_combo.addItems(CUSTOM_XY_ELEMENTS)
        self.y_denom_combo.setSizePolicy(QSizePolicy_Expanding, QSizePolicy_Fixed)
        y_grid.addWidget(self.y_denom_combo, 0, 3)
        custom_xy_layout.addWidget(y_group)

        # Show all numeric fields checkbox
        self.custom_show_all_fields = QCheckBox("Show all numeric fields")
        self.custom_show_all_fields.setChecked(False)
        self.custom_show_all_fields.toggled.connect(self.refresh_custom_xy_combos)
        custom_xy_layout.addWidget(self.custom_show_all_fields)

        # Bubble size (optional third variable, scaled by symbol size)
        custom_xy_layout.addWidget(self._create_bubble_size_group('custom', CUSTOM_XY_ELEMENTS))

        # REE Normalization
        ree_group = QGroupBox("REE Normalization")
        ree_layout = QVBoxLayout(ree_group)
        self.ree_norm_combo = QComboBox()
        self.ree_norm_combo.addItem("None")
        for norm_name, norm_values in NORMALIZATION_OPTIONS:
            self.ree_norm_combo.addItem(norm_name)
        self.ree_norm_combo.setCurrentIndex(0)
        ree_layout.addLayout(self._label_row("Normalization:", self.ree_norm_combo))
        ree_group.setMaximumHeight(70)
        custom_xy_layout.addWidget(ree_group)

        # Axis scales
        scale_row = QHBoxLayout()
        scale_row.setSpacing(20)
        x_scale_label = QLabel("X:")
        x_scale_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        scale_row.addWidget(x_scale_label, 0)
        self.x_scale_combo = QComboBox()
        self.x_scale_combo.addItems(["Linear", "Log"])
        self.x_scale_combo.setSizePolicy(QSizePolicy_Minimum, QSizePolicy_Fixed)
        scale_row.addWidget(self.x_scale_combo, 0)
        y_scale_label = QLabel("Y:")
        y_scale_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        scale_row.addWidget(y_scale_label, 0)
        self.y_scale_combo = QComboBox()
        self.y_scale_combo.addItems(["Linear", "Log"])
        self.y_scale_combo.setSizePolicy(QSizePolicy_Expanding, QSizePolicy_Fixed)
        scale_row.addWidget(self.y_scale_combo, 1)
        custom_xy_layout.addLayout(scale_row)

        self.custom_legend = QCheckBox("Legend")
        self.custom_legend.setChecked(True)
        self.custom_markers = QCheckBox("Markers")
        self.custom_markers.setChecked(True)
        custom_xy_layout.addLayout(self._checkbox_row(self.custom_legend, self.custom_markers))
        custom_xy_layout.addStretch()

        custom_xy_subtabs.addTab(plot_setup_tab, "Plot Setup")

        # Sub-tab: Data Preprocessing (below-detection-limit handling)
        preprocess_tab = QWidget()
        preprocess_layout = QVBoxLayout(preprocess_tab)
        preprocess_layout.setSpacing(5)

        bdl_intro = QLabel(
            "Exploration datasets often code values below detection as negative "
            "numbers (e.g. -5 means “below detection limit of 5”). By "
            "default these plot as literal negative values. Enable below to "
            "substitute them with a positive proxy instead."
        )
        bdl_intro.setWordWrap(True)
        preprocess_layout.addWidget(bdl_intro)

        self.custom_bdl_enabled = QCheckBox("Treat negative values as below-detection-limit codes")
        self.custom_bdl_enabled.setChecked(False)
        preprocess_layout.addWidget(self.custom_bdl_enabled)

        self.custom_bdl_method_combo = QComboBox()
        self.custom_bdl_method_combo.addItems([
            "Half of detection limit",
            "Detection limit",
            "Random value (0 to detection limit)",
            "Fixed value",
        ])
        preprocess_layout.addLayout(self._label_row("Substitution:", self.custom_bdl_method_combo))

        self.custom_bdl_fixed_spin = QDoubleSpinBox()
        self.custom_bdl_fixed_spin.setRange(0.0, 1e9)
        self.custom_bdl_fixed_spin.setDecimals(6)
        self.custom_bdl_fixed_spin.setSingleStep(0.001)
        self.custom_bdl_fixed_spin.setValue(0.001)
        self.custom_bdl_fixed_spin.setEnabled(False)
        preprocess_layout.addLayout(self._label_row("Fixed value:", self.custom_bdl_fixed_spin))

        def _update_bdl_fixed_enabled(text):
            self.custom_bdl_fixed_spin.setEnabled(text == "Fixed value")
        self.custom_bdl_method_combo.currentTextChanged.connect(_update_bdl_fixed_enabled)

        review_btn = QPushButton("Review Negative Values in Selected Fields")
        review_btn.setToolTip(
            "Scan the currently selected samples' X/Y fields for negative "
            "(below-detection) values and show their detection-limit range, "
            "plus a histogram, to help choose an appropriate substitution."
        )
        review_btn.clicked.connect(self._review_custom_xy_negatives)
        preprocess_layout.addWidget(review_btn)

        self.custom_bdl_review_label = QLabel("No review run yet.")
        self.custom_bdl_review_label.setWordWrap(True)
        self.custom_bdl_review_label.setStyleSheet("color: gray; font-style: italic;")
        preprocess_layout.addWidget(self.custom_bdl_review_label)

        preprocess_layout.addStretch()

        custom_xy_subtabs.addTab(preprocess_tab, "Data Preprocessing")

        custom_xy_subtabs.currentChanged.connect(
            lambda idx: self._resize_tab_widget_to_current(idx, custom_xy_subtabs))
        self._resize_tab_widget_to_current(custom_xy_subtabs.currentIndex(), custom_xy_subtabs)

        custom_xy_outer_layout.addWidget(custom_xy_subtabs)

        self.tab_widget.addTab(custom_xy_tab, "Custom XY")

        # Tab 4: Custom Ternary Plot
        custom_tern_tab = QWidget()
        custom_tern_layout = QVBoxLayout(custom_tern_tab)
        custom_tern_layout.setSpacing(5)

        for apex_label, num_attr, denom_attr in [
            ("A (top apex)",   "tern_a_num_combo", "tern_a_denom_combo"),
            ("B (bottom-left apex)", "tern_b_num_combo", "tern_b_denom_combo"),
            ("C (bottom-right apex)", "tern_c_num_combo", "tern_c_denom_combo"),
        ]:
            grp = QGroupBox(apex_label)
            grid = QGridLayout(grp)
            grid.setHorizontalSpacing(20)
            grid.setVerticalSpacing(3)
            num_label = QLabel("Num:")
            num_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
            grid.addWidget(num_label, 0, 0)
            num_combo = QComboBox()
            num_combo.addItems(CUSTOM_XY_ELEMENTS[1:])
            num_combo.setSizePolicy(QSizePolicy_Minimum, QSizePolicy_Fixed)
            grid.addWidget(num_combo, 0, 1)
            denom_label = QLabel("Denom:")
            denom_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
            grid.addWidget(denom_label, 0, 2)
            denom_combo = QComboBox()
            denom_combo.addItems(CUSTOM_XY_ELEMENTS)
            denom_combo.setSizePolicy(QSizePolicy_Expanding, QSizePolicy_Fixed)
            grid.addWidget(denom_combo, 0, 3)
            setattr(self, num_attr, num_combo)
            setattr(self, denom_attr, denom_combo)
            custom_tern_layout.addWidget(grp)

        self.tern_show_all_fields = QCheckBox("Show all numeric fields")
        self.tern_show_all_fields.setChecked(False)
        self.tern_show_all_fields.toggled.connect(self.refresh_custom_ternary_combos)
        custom_tern_layout.addWidget(self.tern_show_all_fields)

        self.tern_legend = QCheckBox("Legend")
        self.tern_legend.setChecked(True)
        self.tern_markers = QCheckBox("Markers")
        self.tern_markers.setChecked(True)
        custom_tern_layout.addLayout(self._checkbox_row(self.tern_legend, self.tern_markers))

        custom_tern_layout.addWidget(self._create_bubble_size_group('tern', CUSTOM_XY_ELEMENTS))
        custom_tern_layout.addStretch()

        self.tab_widget.addTab(custom_tern_tab, "Custom Ternary")

        # Tab 5: Minerals (mineral classification plots)
        minerals_tab = QWidget()
        minerals_layout = QVBoxLayout(minerals_tab)
        minerals_layout.setSpacing(5)

        self.minerals_combo = QComboBox()
        self.minerals_combo.addItems(list(MINERALS_DIAGRAMS.keys()))
        minerals_layout.addWidget(self.minerals_combo)

        self.minerals_legend = QCheckBox("Field Legend")
        self.minerals_legend.setChecked(True)
        self.minerals_category_legend = QCheckBox("Category Legend")
        self.minerals_category_legend.setChecked(True)
        minerals_layout.addLayout(self._checkbox_row(self.minerals_legend, self.minerals_category_legend))

        minerals_layout.addWidget(self._create_bubble_size_group('minerals', CUSTOM_XY_ELEMENTS, editable=True))
        minerals_layout.addStretch()

        self.tab_widget.addTab(minerals_tab, "Minerals")

        # Tab 6: Petrophysics
        petro_tab = QWidget()
        petro_layout = QVBoxLayout(petro_tab)
        petro_layout.setSpacing(5)

        # X Axis (Density)
        petro_x_group = QGroupBox("X-Axis (Density)")
        petro_x_grid = QGridLayout(petro_x_group)
        petro_x_grid.setHorizontalSpacing(20)
        petro_x_grid.setVerticalSpacing(3)
        petro_x_field_label = QLabel("Field:")
        petro_x_field_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        petro_x_grid.addWidget(petro_x_field_label, 0, 0)
        self.petro_x_field_combo = QComboBox()
        self.petro_x_field_combo.setSizePolicy(QSizePolicy_Expanding, QSizePolicy_Fixed)
        petro_x_grid.addWidget(self.petro_x_field_combo, 0, 1, 1, 3)
        petro_x_units_label = QLabel("Units:")
        petro_x_units_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        petro_x_grid.addWidget(petro_x_units_label, 1, 0)
        self.petro_x_unit_combo = QComboBox()
        self.petro_x_unit_combo.addItems([
            "No Scaling",
            "CGS (no scaling)",
            "SI (÷ 1000)",
        ])
        self.petro_x_unit_combo.setSizePolicy(QSizePolicy_Expanding, QSizePolicy_Fixed)
        petro_x_grid.addWidget(self.petro_x_unit_combo, 1, 1, 1, 3)
        petro_layout.addWidget(petro_x_group)

        # Y Axis (Magnetic Susceptibility)
        petro_y_group = QGroupBox("Y-Axis (Magnetic Susceptibility)")
        petro_y_grid = QGridLayout(petro_y_group)
        petro_y_grid.setHorizontalSpacing(20)
        petro_y_grid.setVerticalSpacing(3)
        petro_y_field_label = QLabel("Field:")
        petro_y_field_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        petro_y_grid.addWidget(petro_y_field_label, 0, 0)
        self.petro_y_field_combo = QComboBox()
        self.petro_y_field_combo.setSizePolicy(QSizePolicy_Expanding, QSizePolicy_Fixed)
        petro_y_grid.addWidget(self.petro_y_field_combo, 0, 1, 1, 3)
        petro_y_units_label = QLabel("Units:")
        petro_y_units_label.setSizePolicy(QSizePolicy_Fixed, QSizePolicy_Fixed)
        petro_y_grid.addWidget(petro_y_units_label, 1, 0)
        self.petro_y_unit_combo = QComboBox()
        self.petro_y_unit_combo.addItems([
            "No Scaling",
            "CGS (× 4π)",
            "SI (no scaling)",
            "SI ×10⁻³",
        ])
        self.petro_y_unit_combo.setSizePolicy(QSizePolicy_Expanding, QSizePolicy_Fixed)
        petro_y_grid.addWidget(self.petro_y_unit_combo, 1, 1, 1, 3)
        petro_layout.addWidget(petro_y_group)

        self.petro_legend = QCheckBox("Legend")
        self.petro_legend.setChecked(True)
        self.petro_markers = QCheckBox("Markers")
        self.petro_markers.setChecked(True)
        petro_layout.addLayout(self._checkbox_row(self.petro_legend, self.petro_markers))

        petro_layout.addWidget(self._create_bubble_size_group('petro', ['1 (none)']))
        petro_layout.addStretch()

        self.tab_widget.addTab(petro_tab, "Petrophysics")

        # Shrink the tab widget to each tab's own content height instead of
        # always reserving space for the tallest tab, so short tabs don't
        # show a block of empty space above the "Samples" section below.
        self.tab_widget.currentChanged.connect(self._resize_tab_widget_to_current)
        self._resize_tab_widget_to_current(self.tab_widget.currentIndex())

        main_layout.addWidget(self.tab_widget)

        # Sample selection
        sample_group = QGroupBox("Samples")
        sample_layout = QVBoxLayout(sample_group)
        sample_layout.setSpacing(3)
        
        self.feature_list = QListWidget()
        self.feature_list.setSelectionMode(QListWidget_MultiSelection)
        self.feature_list.setMaximumHeight(150)
        sample_layout.addWidget(self.feature_list)

        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("All")
        select_all_btn.clicked.connect(self.select_all_features)
        deselect_all_btn = QPushButton("None")
        deselect_all_btn.clicked.connect(self.deselect_all_features)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_selection)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(select_all_btn)
        btn_row.addWidget(deselect_all_btn)
        sample_layout.addLayout(btn_row)

        classify_btn = QPushButton("Add Classification Field to Layer")
        classify_btn.setToolTip(
            "Adds (or updates) a text field in the layer with the classification\n"
            "domain for every feature based on the selected diagram."
        )
        classify_btn.clicked.connect(self.add_classification_field)
        sample_layout.addWidget(classify_btn)

        filter_row = QHBoxLayout()
        filter_to_selection_btn = QPushButton("Filter Layer to Selected")
        filter_to_selection_btn.setToolTip(
            "Restrict the layer to only the samples currently selected in QGIS\n"
            "(e.g. via lasso/rectangle-select on a plot), so the sample list,\n"
            "plots and the attribute table only see those features."
        )
        filter_to_selection_btn.clicked.connect(self.filter_layer_to_selection)
        clear_filter_btn = QPushButton("Clear Filter")
        clear_filter_btn.setToolTip("Remove the filter and show all features in the layer again.")
        clear_filter_btn.clicked.connect(self.clear_layer_filter)
        filter_row.addWidget(filter_to_selection_btn)
        filter_row.addWidget(clear_filter_btn)
        sample_layout.addLayout(filter_row)

        main_layout.addWidget(sample_group)

        # Action buttons
        button_layout = QHBoxLayout()
        plot_btn = QPushButton("Generate Plot")
        plot_btn.clicked.connect(self.generate_plot)
        button_layout.addWidget(plot_btn)
        save_btn = QPushButton("Save...")
        save_btn.clicked.connect(self.save_plot)
        button_layout.addWidget(save_btn)
        main_layout.addLayout(button_layout)

        # Wrap in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(main_widget)
        scroll_area.setWidgetResizable(True)
        # Horizontal scrolling was previously disabled outright, so content
        # wider than the docked panel (long layer/field names, etc.) was
        # simply clipped with no way to see the rest. A scrollbar that only
        # appears when needed fixes that without changing the normal layout.
        scroll_area.setHorizontalScrollBarPolicy(Qt_ScrollBarAsNeeded)
        self.setWidget(scroll_area)
        self.setMinimumWidth(320)

    def _all_possible_geochemical_variables(self):
        """Return all geochemical variables recognised by the plotting tool."""
        variables = set()

        for _, values in NORMALIZATION_OPTIONS:
            variables.update(values.keys())

        variables.update(EXTENDED_SPIDER_ORDER)
        variables.update(EXTENDED_ORDER_ALT)
        variables.update(REE_ORDER)
        variables.update(REE_ELEMENTS)
        variables.update([v for v in CUSTOM_XY_ELEMENTS if v not in ('1 (none)', 'Mg#')])

        return sorted(variables)

    def _has_petrophysical_field(self, layer):
        """Return True if the layer contains density or magnetic-susceptibility fields."""
        density_tokens = (
            'density', 'dens', 'bulk_density', 'dry_density', 'wet_density',
            'rho', 'specific_gravity', 'specificgravity', 'sg'
        )
        magnetic_susceptibility_tokens = (
            'magnetic_susceptibility', 'mag_susceptibility', 'mag_susc',
            'mag_sus', 'magsus', 'susceptibility', 'kappa'
        )
        magnetic_susceptibility_exact = {'ms', 'magsus', 'mag_sus', 'mag_susc', 'k'}

        for field in layer.fields():
            name = field.name().strip().lower()
            normalised = re.sub(r'[^a-z0-9]+', '_', name).strip('_')

            if any(token in normalised for token in density_tokens):
                return True
            if any(token in normalised for token in magnetic_susceptibility_tokens):
                return True
            if normalised in magnetic_susceptibility_exact:
                return True
            if 'mag' in normalised and 'sus' in normalised:
                return True

        return False

    def _is_candidate_data_layer(self, layer):
        """Return True for layers that can plausibly feed geochemical/petrophysical plots."""
        if not isinstance(layer, QgsVectorLayer):
            return False

        matched_variables = set()
        for variable in self._all_possible_geochemical_variables():
            if find_element_field(layer, variable):
                matched_variables.add(variable)
                if len(matched_variables) >= 2:
                    return True

        return self._has_petrophysical_field(layer)

    def load_layers(self):
        """Load vector layers containing geochemical or petrophysical data into the combo box."""
        self.layer_combo.blockSignals(True)
        current_layer_id = self.layer_combo.currentData()
        self.layer_combo.clear()
        
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if self._is_candidate_data_layer(layer):
                self.layer_combo.addItem(layer.name(), layer.id())
        
        # Try to restore previous selection
        if current_layer_id:
            index = self.layer_combo.findData(current_layer_id)
            if index >= 0:
                self.layer_combo.setCurrentIndex(index)
        
        self.layer_combo.blockSignals(False)
        
        if self.layer_combo.count() > 0:
            self.on_layer_changed(self.layer_combo.currentIndex())

    def on_layer_changed(self, index):
        """Handle layer selection change."""
        if index < 0:
            return
        
        layer_id = self.layer_combo.itemData(index)
        if layer_id is None:
            return
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            return
        
        self.id_field_combo.clear()
        self.label_field_combo.clear()
        self.id_field_combo.addItem(NO_CATEGORY_OPTION)
        field_names = [field.name() for field in layer.fields()]
        for field_name in field_names:
            self.id_field_combo.addItem(field_name)
            self.label_field_combo.addItem(field_name)

        # Auto-select ID field. Default to "no category" (single shared
        # symbol) unless a recognisable sample/category field is found.
        preferred_names = ['sample_id', 'sampleid', 'sample', 'name', 'id', 'sample_name',
                        'samplename', 'label', 'station', 'site', 'sample_no', 'samp_id',
                        'hole_id', 'holeid', 'drillhole', 'core_id', 'spec_id', 'specimen']
        best_index = 0  # NO_CATEGORY_OPTION

        for pref in preferred_names:
            for i, fn in enumerate(field_names):
                if fn.lower() == pref.lower():
                    best_index = i + 1  # +1 for the leading NO_CATEGORY_OPTION entry
                    break
            else:
                continue
            break

        self.id_field_combo.setCurrentIndex(best_index)
        self.update_feature_list(layer)

        # Refresh custom XY dropdowns if showing all numeric fields
        self.refresh_custom_xy_combos()
        self.refresh_petrophysics_combos()

        
    def on_layer_changed_old(self, index):
        """Handle layer selection change."""
        if index < 0:
            return
        
        layer_id = self.layer_combo.itemData(index)
        if layer_id is None:
            return
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            return
        
        self.id_field_combo.clear()
        field_names = [field.name() for field in layer.fields()]
        for field_name in field_names:
            self.id_field_combo.addItem(field_name)
        
        # Auto-select ID field
        preferred_names = ['sample_id', 'sampleid', 'sample', 'name', 'id', 'sample_name', 
                          'samplename', 'label', 'station', 'site', 'sample_no', 'samp_id',
                          'hole_id', 'holeid', 'drillhole', 'core_id', 'spec_id', 'specimen']
        best_index = 0
        
        for pref in preferred_names:
            for i, fn in enumerate(field_names):
                if fn.lower() == pref.lower():
                    best_index = i
                    break
            else:
                continue
            break
        
        self.id_field_combo.setCurrentIndex(best_index)
        self.update_feature_list(layer)

    def on_id_field_changed(self, index):
        """Handle ID field selection change."""
        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer:
            self.update_feature_list(layer)

    def _category_field_label(self):
        """Return a clean template-key label for the current 'Category:' selection."""
        id_field = self.id_field_combo.currentText()
        if not id_field or id_field == NO_CATEGORY_OPTION:
            return NO_CATEGORY_LABEL
        return id_field

    def update_feature_list(self, layer):
        """Update the feature list."""
        self.feature_list.setUpdatesEnabled(False)
        self.feature_list.clear()
        id_field = self.id_field_combo.currentText()
        
        selected_ids = set(layer.selectedFeatureIds())
        field_names = [f.name() for f in layer.fields()]
        use_id_field = id_field and id_field in field_names
        
        items_to_add = []
        
        for feature in layer.getFeatures():
            label = None
            fid = feature.id()
            
            if use_id_field:
                value = feature[id_field]
                if value is not None and value != NULL and str(value).strip() not in ('', 'NULL', 'None'):
                    label = str(value)
            
            if label is None:
                label = f"Feature {fid}"
            
            items_to_add.append((label, fid))
        
        items_to_add.sort(key=lambda x: x[0].lower())
        
        items_to_select = []
        for label, fid in items_to_add:
            item = QListWidgetItem(label)
            item.setData(Qt_UserRole, fid)
            self.feature_list.addItem(item)
            
            if fid in selected_ids:
                items_to_select.append(item)
        
        for item in items_to_select:
            item.setSelected(True)
        
        self.feature_list.setUpdatesEnabled(True)

    def select_all_features(self):
        """Select all features."""
        for i in range(self.feature_list.count()):
            self.feature_list.item(i).setSelected(True)

    def deselect_all_features(self):
        """Deselect all features."""
        for i in range(self.feature_list.count()):
            self.feature_list.item(i).setSelected(False)

    def refresh_selection(self):
        """Refresh feature list from QGIS selection."""
        layer_id = self.layer_combo.currentData()
        if layer_id is None:
            return
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer:
            self.update_feature_list(layer)

    def _build_fid_subset_string(self, layer, feature_ids):
        """Build a data-provider WHERE clause selecting exactly `feature_ids`.

        Prefers the layer's declared primary key field (robust for PostGIS/
        Spatialite/GeoPackage layers); falls back to OGR's special FID
        pseudo-column, which file-based providers (Shapefile, GeoPackage,
        CSV, ...) accept even without a declared primary key.
        """
        try:
            pk_indexes = layer.dataProvider().pkAttributeIndexes()
        except Exception:
            pk_indexes = []

        if pk_indexes:
            pk_field = layer.fields()[pk_indexes[0]].name()
            values = []
            for fid in feature_ids:
                feature = layer.getFeature(fid)
                if not feature.isValid():
                    continue
                val = feature[pk_field]
                if isinstance(val, (int, float)):
                    values.append(str(val))
                else:
                    values.append("'{}'".format(str(val).replace("'", "''")))
            if values:
                return '"{}" IN ({})'.format(pk_field, ','.join(values))

        id_list = ','.join(str(fid) for fid in feature_ids)
        return f"FID IN ({id_list})"

    def filter_layer_to_selection(self):
        """Restrict the current layer to only its currently-selected features.

        Uses the layer's own selection (e.g. set by lasso/rectangle-select on
        a plot), so subsequent plots, the sample list and the attribute table
        only see the selected samples.
        """
        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            QMessageBox.warning(self, "Warning", "Please select a valid layer.")
            return

        selected_ids = layer.selectedFeatureIds()
        if not selected_ids:
            QMessageBox.warning(self, "Warning",
                "No features are selected. Select samples in QGIS first "
                "(e.g. lasso/rectangle-select on a plot), then filter.")
            return

        subset = self._build_fid_subset_string(layer, selected_ids)
        if not layer.setSubsetString(subset):
            QMessageBox.warning(self, "Filter failed",
                "Could not filter this layer's data source to the selection.\n"
                "This can happen with some data providers. As an alternative, "
                "use QGIS's Export > Save Selected Features As... to create a "
                "new layer from the selection.")
            return

        self.update_feature_list(layer)
        QMessageBox.information(self, "Filter applied",
            f"Layer filtered to {len(selected_ids)} selected sample(s).\n"
            "Use \"Clear Filter\" to show all features again.")

    def clear_layer_filter(self):
        """Remove any filter applied by "Filter Layer to Selected", restoring all features."""
        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            QMessageBox.warning(self, "Warning", "Please select a valid layer.")
            return
        if not layer.subsetString():
            QMessageBox.information(self, "No filter", "This layer isn't currently filtered.")
            return
        if not layer.setSubsetString(''):
            QMessageBox.warning(self, "Error", "Could not clear the filter on this layer.")
            return
        self.update_feature_list(layer)

    def get_element_order(self):
        """Get the element order for spider diagrams."""
        index = self.order_combo.currentIndex()
        if index == 1:
            return EXTENDED_SPIDER_ORDER
        elif index == 0:
            return REE_ORDER
        return EXTENDED_ORDER_ALT

    def get_normalization_info(self):
        """Get selected normalisation label and values for spider diagrams."""
        norm_values = self.norm_combo.currentData()
        norm_name = self.norm_combo.currentText()
        if norm_values is None:
            norm_name, norm_values = NORMALIZATION_OPTIONS[0]
        return norm_name, norm_values

    def get_normalization_values(self):
        """Get selected normalisation values."""
        return self.get_normalization_info()[1]

    def generate_plot(self):
        """Generate the selected plot type."""
        if not MATPLOTLIB_AVAILABLE:
            QMessageBox.critical(self, "Error", "matplotlib is not installed.")
            return

        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            QMessageBox.warning(self, "Warning", "Please select a valid layer.")
            return

        selected_items = self.feature_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select at least one sample.")
            return

        id_field = self.id_field_combo.currentText()
        use_category_field = bool(id_field) and id_field != NO_CATEGORY_OPTION
        features = []
        sample_names = []
        for item in selected_items:
            fid = item.data(Qt_UserRole)
            feature = layer.getFeature(fid)
            features.append(feature)
            if use_category_field:
                sample_names.append(str(feature[id_field]))
            else:
                sample_names.append(NO_CATEGORY_LABEL)

        plt.ion()
        
        if self.tab_widget.currentIndex() == 0:
            self.generate_spider_diagram(layer, features, sample_names)
        elif self.tab_widget.currentIndex() == 1:
            self.generate_discrimination_diagram(layer, features, sample_names)
        elif self.tab_widget.currentIndex() == 2:
            self.generate_custom_xy_plot(layer, features, sample_names)
        elif self.tab_widget.currentIndex() == 3:
            self.generate_custom_ternary_plot(layer, features, sample_names)
        elif self.tab_widget.currentIndex() == 4:
            self.generate_minerals_plot(layer, features, sample_names)
        elif self.tab_widget.currentIndex() == 5:
            self.generate_petrophysics_plot(layer, features, sample_names)

    def generate_spider_diagram(self, layer, features, sample_names):
        """Generate spider diagram."""
        element_order = self.get_element_order()
        norm_name, norm_values = self.get_normalization_info()

        size_field, bubble_active, bubble_min_size, bubble_max_size, bubble_method = \
            self._read_bubble_controls('spider')
        size_data = [get_custom_element_value(feature, layer, size_field) if bubble_active else None
                    for feature in features]
        bubble_vmin = bubble_vmax = None
        if bubble_active:
            bubble_vmin, bubble_vmax, bubble_active = self._compute_bubble_range(
                'spider', size_data, [True] * len(size_data), bubble_method)

        missing_from_normalisation = [
            element for element in element_order
            if element not in norm_values or norm_values.get(element) is None or norm_values.get(element, 0) <= 0
        ]
        missing_from_dataset = []
        no_usable_values = []

        plot_data = []
        for feature_index, feature in enumerate(features):
            normalized_values = []
            for element in element_order:
                value = np.nan
                if find_element_field(layer, element) is None:
                    if element not in missing_from_dataset:
                        missing_from_dataset.append(element)
                    normalized_values.append(value)
                    continue

                # Auto-converts ppb/pct/oxide-wt% to elemental ppm as needed,
                # regardless of which unit or elemental/oxide form is present.
                raw_value = get_element_ppm(feature, layer, element)
                if raw_value is not None and raw_value > 0 and element in norm_values and norm_values[element] > 0:
                    value = raw_value / norm_values[element]
                normalized_values.append(value)
            plot_data.append(normalized_values)

        for element_index, element in enumerate(element_order):
            if element in missing_from_dataset or element in missing_from_normalisation:
                continue
            if not any(np.isfinite(values[element_index]) for values in plot_data):
                no_usable_values.append(element)

        warning_sections = []
        if missing_from_normalisation:
            warning_sections.append(
                "Missing from the selected normalisation ({}):\n{}".format(
                    norm_name, ", ".join(missing_from_normalisation)
                )
            )
        if missing_from_dataset:
            warning_sections.append(
                "Missing from the selected dataset/layer fields:\n{}".format(
                    ", ".join(missing_from_dataset)
                )
            )
        if no_usable_values:
            warning_sections.append(
                "Present in the dataset and the normalisation option, but with no usable positive values in the selected samples:\n{}".format(
                    ", ".join(no_usable_values)
                )
            )

        if warning_sections:
            QMessageBox.warning(
                self,
                "Incomplete spider-diagram normalisation",
                "Some elements cannot be plotted for the selected spider diagram.\n\n" + "\n\n".join(warning_sections)
            )

        fig, ax = plt.subplots(figsize=(12, 8))
        x_positions = np.arange(len(element_order))

        category_styles, unique_categories = self._build_default_category_styles(sample_names)
        category_colors, category_markers, sample_colors, sample_markers = \
            self._category_arrays_from_styles(category_styles, sample_names)

        plotted_categories = set()
        line_to_fid = {}
        artist_registry = {}

        for i, (values, name, feature) in enumerate(zip(plot_data, sample_names, features)):
            marker = sample_markers[i] if self.spider_markers.isChecked() else None
            color = sample_colors[i]
            label = name if name not in plotted_categories else None
            plotted_categories.add(name)

            if bubble_active:
                sv = size_data[i]
                area = (bubble_symbol_size(sv, bubble_vmin, bubble_vmax, bubble_min_size,
                                           bubble_max_size, bubble_method)
                        if sv is not None else bubble_min_size)
                line_markersize = math.sqrt(area)
            else:
                line_markersize = 8

            lines = ax.plot(x_positions, values, marker=marker, markersize=line_markersize, linewidth=1.5,
                   label=label, color=color, markerfacecolor='white' if marker else None,
                   markeredgecolor=color, markeredgewidth=1.5)
            line_to_fid[lines[0]] = feature.id()
            artist_registry.setdefault(name, []).append({'artist': lines[0], 'role': 'marker'})

        ax.set_yscale('log')
        ax.set_xlim(-0.5, len(element_order) - 0.5)
        ax.set_ylim(0.1, 1000)
        ax.set_xticks(x_positions)
        ax.set_xticklabels(element_order, fontsize=10)

        ax.set_ylabel(f'Sample / {norm_name}', fontsize=12)
        ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
        ax.yaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=10))
        ax.grid(True, which='major', axis='y', linestyle='-', alpha=0.3)
        ax.grid(True, which='minor', axis='y', linestyle=':', alpha=0.2)

        n_samples = len(plot_data)
        ax.set_title(f'Multi-Element Spider Diagram (n={n_samples})\nNormalised to {norm_name}', fontsize=14)

        category_counts = Counter(sample_names)
        export_legend_artists = {}
        category_legend_obj = None
        if self.spider_legend.isChecked():
            export_legend_artists = self._build_category_legend(
                ax, unique_categories, category_styles, category_counts,
                bbox_to_anchor=(0.5, -0.12), fontsize=9)
            category_legend_obj = ax.get_legend()

        if bubble_active:
            self._add_bubble_size_legend(
                ax, bubble_vmin, bubble_vmax, bubble_min_size, bubble_max_size, bubble_method,
                self._field_display_label(size_field), category_legend_obj)

        plt.tight_layout()
        fig.subplots_adjust(bottom=0.25)
        plt.show()
        self._attach_spider_selection(fig, line_to_fid, layer.id())
        self._open_category_panel(
            fig, artist_registry, category_counts=category_counts, category_styles=category_styles,
            style_template_key=self._category_field_label(), export_legend_artists=export_legend_artists,
            title='Spider Diagram Categories', bubble_active=bubble_active)
        self.current_fig = fig

    def add_classification_field(self):
        """Add or update a classification field on the layer for the current discrimination diagram."""
        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            QMessageBox.warning(self, "Warning", "Please select a valid layer.")
            return

        if self.tab_widget.currentIndex() == 4:
            diagram_class = MINERALS_DIAGRAMS[self.minerals_combo.currentText()]
        else:
            diagram_name = self.diagram_combo.currentText()
            diagram_class = DISCRIMINATION_DIAGRAMS[diagram_name]
        field_name = diagram_class.field_name

        if not layer.isEditable():
            if not layer.startEditing():
                QMessageBox.critical(self, "Error",
                    f"Cannot edit layer '{layer.name()}'. Make sure it is not read-only.")
                return

        # Add the field if it doesn't exist yet
        if layer.fields().indexOf(field_name) < 0:
            layer.addAttribute(QgsField(field_name, QVariant.String, len=64))
            layer.updateFields()

        field_idx = layer.fields().indexOf(field_name)
        if field_idx < 0:
            QMessageBox.critical(self, "Error", f"Could not create field '{field_name}'.")
            layer.rollBack()
            return

        # Classify every feature in the layer
        n_classified = 0
        for feature in layer.getFeatures():
            coords = diagram_class.calculate_coordinates(feature, layer)
            label = diagram_class.classify_point(*coords)
            layer.changeAttributeValue(feature.id(), field_idx, label)
            if label is not None:
                n_classified += 1

        layer.commitChanges()
        layer.updateFields()

        total = layer.featureCount()
        QMessageBox.information(
            self, "Classification Complete",
            f"Field '{field_name}' written to layer '{layer.name()}'.\n"
            f"{n_classified} of {total} features assigned a domain label.\n"
            f"Features outside all known fields have NULL."
        )

        # Add the new field to the category dropdown if not already present, then select it
        existing_fields = [self.id_field_combo.itemText(i) for i in range(self.id_field_combo.count())]
        if field_name not in existing_fields:
            self.id_field_combo.addItem(field_name)
        self.id_field_combo.setCurrentText(field_name)

    def generate_discrimination_diagram(self, layer, features, sample_names):
        """Generate discrimination diagram."""
        diagram_name = self.diagram_combo.currentText()
        diagram_class = DISCRIMINATION_DIAGRAMS[diagram_name]

        size_field, bubble_active, bubble_min_size, bubble_max_size, bubble_method = \
            self._read_bubble_controls('discrim')

        data = []
        size_data = []
        for feature in features:
            coords = diagram_class.calculate_coordinates(feature, layer)
            data.append(coords)
            size_data.append(get_custom_element_value(feature, layer, size_field) if bubble_active else None)

        valid_count = sum(1 for coords in data if coords[0] is not None)

        # Build pts_data and fid_list for selection (handles both binary and ternary)
        pts_data = []
        fid_list = []
        valid_mask = []
        for coords, feature in zip(data, features):
            if coords[0] is None:
                valid_mask.append(False)
                continue
            if len(coords) == 3:
                if coords[2] is None:
                    valid_mask.append(False)
                    continue
                x, y = ternary_to_cartesian(*coords)
            else:
                if coords[1] is None:
                    valid_mask.append(False)
                    continue
                x, y = coords[0], coords[1]
            valid_mask.append(True)
            pts_data.append((x, y))
            fid_list.append(feature.id())

        bubble_vmin = bubble_vmax = None
        if bubble_active:
            bubble_vmin, bubble_vmax, bubble_active = self._compute_bubble_range(
                'discrim', size_data, valid_mask, bubble_method)
        sample_sizes = None
        if bubble_active:
            sample_sizes = [
                bubble_symbol_size(v, bubble_vmin, bubble_vmax, bubble_min_size, bubble_max_size, bubble_method)
                if v is not None else bubble_min_size
                for v in size_data
            ]

        category_styles, unique_categories = self._build_default_category_styles(sample_names)
        category_colors, category_markers, sample_colors, sample_markers = \
            self._category_arrays_from_styles(category_styles, sample_names)

        fig, ax = plt.subplots(figsize=(10, 8))
        fid_to_scatter, category_artists = diagram_class.plot(ax, data, sample_names,
                          show_legend=self.discrim_legend.isChecked(),
                          show_category_legend=self.discrim_category_legend.isChecked(),
                          sample_colors=sample_colors, category_colors=category_colors,
                          sample_markers=sample_markers, category_markers=category_markers,
                          n_samples=valid_count, fids=fid_list, sample_sizes=sample_sizes)
        artist_registry = {cat: [{'artist': a, 'role': 'scatter'} for a in arts]
                           for cat, arts in category_artists.items()}
        export_legend_artists = self._extract_legend_artists(ax.get_legend())
        if bubble_active:
            self._add_bubble_size_legend(
                ax, bubble_vmin, bubble_vmax, bubble_min_size, bubble_max_size, bubble_method,
                self._field_display_label(size_field), ax.get_legend())
        plt.tight_layout()
        fig.subplots_adjust(bottom=0.2)
        plt.show()
        self._attach_scatter_selection(fig, ax, pts_data, fid_list, fid_to_scatter, layer.id())
        self._open_category_panel(
            fig, artist_registry, category_counts=Counter(sample_names), category_styles=category_styles,
            style_template_key=self._category_field_label(), export_legend_artists=export_legend_artists,
            title='Discrimination Diagram Categories', bubble_active=bubble_active)
        self.current_fig = fig

    def generate_minerals_plot(self, layer, features, sample_names):
        """Generate the selected mineral classification plot."""
        minerals_name = self.minerals_combo.currentText()
        minerals_class = MINERALS_DIAGRAMS[minerals_name]

        size_field, bubble_active, bubble_min_size, bubble_max_size, bubble_method = \
            self._read_bubble_controls('minerals')

        data = []
        size_data = []
        for feature in features:
            coords = minerals_class.calculate_coordinates(feature, layer)
            data.append(coords)
            size_data.append(get_custom_element_value(feature, layer, size_field) if bubble_active else None)

        valid_count = sum(1 for coords in data if coords[0] is not None)
        if valid_count == 0:
            QMessageBox.warning(self, "Warning",
                "No valid data points. Layer needs La, Ce, Pr, Nd, Sr and Y fields.")
            return

        pts_data = []
        fid_list = []
        valid_mask = []
        for coords, feature in zip(data, features):
            if coords[0] is None or coords[1] is None:
                valid_mask.append(False)
                continue
            valid_mask.append(True)
            pts_data.append((coords[0], coords[1]))
            fid_list.append(feature.id())

        bubble_vmin = bubble_vmax = None
        if bubble_active:
            bubble_vmin, bubble_vmax, bubble_active = self._compute_bubble_range(
                'minerals', size_data, valid_mask, bubble_method)
        sample_sizes = None
        if bubble_active:
            sample_sizes = [
                bubble_symbol_size(v, bubble_vmin, bubble_vmax, bubble_min_size, bubble_max_size, bubble_method)
                if v is not None else bubble_min_size
                for v in size_data
            ]

        category_styles, unique_categories = self._build_default_category_styles(sample_names)
        category_colors, category_markers, sample_colors, sample_markers = \
            self._category_arrays_from_styles(category_styles, sample_names)

        fig, ax = plt.subplots(figsize=(10, 8))
        fid_to_scatter, category_artists = minerals_class.plot(
            ax, data, sample_names,
            show_legend=self.minerals_legend.isChecked(),
            show_category_legend=self.minerals_category_legend.isChecked(),
            sample_colors=sample_colors, category_colors=category_colors,
            sample_markers=sample_markers, category_markers=category_markers,
            n_samples=valid_count, fids=fid_list, sample_sizes=sample_sizes)
        artist_registry = {cat: [{'artist': a, 'role': 'scatter'} for a in arts]
                           for cat, arts in category_artists.items()}
        export_legend_artists = self._extract_legend_artists(ax.get_legend())
        if bubble_active:
            self._add_bubble_size_legend(
                ax, bubble_vmin, bubble_vmax, bubble_min_size, bubble_max_size, bubble_method,
                self._field_display_label(size_field), ax.get_legend())
        plt.tight_layout()
        fig.subplots_adjust(bottom=0.2)
        plt.show()
        self._attach_scatter_selection(fig, ax, pts_data, fid_list, fid_to_scatter, layer.id())
        self._open_category_panel(
            fig, artist_registry, category_counts=Counter(sample_names), category_styles=category_styles,
            style_template_key=self._category_field_label(), export_legend_artists=export_legend_artists,
            title='Mineral Classification Categories', bubble_active=bubble_active)
        self.current_fig = fig

    def generate_petrophysics_plot(self, layer, features, sample_names):
        """Generate petrophysics scatter plot (density vs magnetic susceptibility)."""
        import math

        x_field = self.petro_x_field_combo.currentText()
        y_field = self.petro_y_field_combo.currentText()

        if not x_field or not y_field:
            QMessageBox.warning(self, "Warning", "Please select fields for both axes.")
            return

        # Density (X) scaling
        x_unit_idx = self.petro_x_unit_combo.currentIndex()
        if x_unit_idx == 2:     # SI (÷ 1000)
            x_factor = 1.0 / 1000.0
            x_unit_label = " (SI, kg/m³)"
        else:                   # No Scaling or CGS — both use raw value
            x_factor = 1.0
            x_unit_label = " (CGS, g/cm³)" if x_unit_idx == 1 else ""

        # Magnetic susceptibility (Y) scaling
        y_unit_idx = self.petro_y_unit_combo.currentIndex()
        if y_unit_idx == 1:     # CGS (× 4π)
            y_factor = 4.0 * math.pi
            y_unit_label = " (CGS)"
        elif y_unit_idx == 3:   # SI ×10⁻³
            y_factor = 1e-3
            y_unit_label = " (SI ×10⁻³)"
        else:                   # No Scaling or SI — both use raw value
            y_factor = 1.0
            y_unit_label = " (SI)" if y_unit_idx == 2 else ""

        size_field, bubble_active, bubble_min_size, bubble_max_size, bubble_method = \
            self._read_bubble_controls('petro')

        x_data, y_data, size_data = [], [], []
        valid_count = 0
        for feature in features:
            try:
                xv = feature[x_field]
                xv = float(xv) * x_factor if xv is not None and xv != NULL else None
            except (ValueError, TypeError):
                xv = None
            try:
                yv = feature[y_field]
                yv = float(yv) * y_factor if yv is not None and yv != NULL else None
            except (ValueError, TypeError):
                yv = None
            x_data.append(xv)
            y_data.append(yv)
            if bubble_active:
                try:
                    sv = feature[size_field]
                    sv = float(sv) if sv is not None and sv != NULL else None
                except (ValueError, TypeError):
                    sv = None
            else:
                sv = None
            size_data.append(sv)
            if xv is not None and yv is not None:
                valid_count += 1

        if valid_count == 0:
            QMessageBox.warning(self, "Warning", "No valid data points to plot.")
            return

        valid_mask = [x is not None and y is not None for x, y in zip(x_data, y_data)]
        bubble_vmin = bubble_vmax = None
        if bubble_active:
            bubble_vmin, bubble_vmax, bubble_active = self._compute_bubble_range(
                'petro', size_data, valid_mask, bubble_method)

        category_styles, unique_categories = self._build_default_category_styles(sample_names)
        category_colors, category_markers, sample_colors, sample_markers = \
            self._category_arrays_from_styles(category_styles, sample_names)

        fig, ax = plt.subplots(figsize=(12, 9))

        ax.set_yscale('log')

        default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        plotted_categories = set()
        pts_data, fid_list = [], []
        fid_to_scatter = {}
        artist_registry = {}

        cat_groups = {}
        for i, (x, y, name, feature) in enumerate(zip(x_data, y_data, sample_names, features)):
            if x is None or y is None:
                continue
            color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
            marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
            cat_key = (name, marker) if self.petro_markers.isChecked() else name
            if cat_key not in cat_groups:
                cat_groups[cat_key] = {'xs': [], 'ys': [], 'fids': [], 'colors': [], 'sizes': [],
                                       'marker': marker, 'name': name}
            g = cat_groups[cat_key]
            g['xs'].append(x); g['ys'].append(y)
            g['fids'].append(feature.id()); g['colors'].append(color)
            if bubble_active:
                sv = size_data[i]
                size = (bubble_symbol_size(sv, bubble_vmin, bubble_vmax, bubble_min_size,
                                           bubble_max_size, bubble_method)
                        if sv is not None else bubble_min_size)
            else:
                size = 80
            g['sizes'].append(size)
            pts_data.append((x, y))
            fid_list.append(feature.id())

        for g in cat_groups.values():
            label = None
            if self.petro_legend.isChecked() and g['name'] not in plotted_categories:
                label = g['name']
                plotted_categories.add(g['name'])
            scatter_kw = dict(s=g['sizes'], c=g['colors'], edgecolors='black',
                              linewidths=0.5, zorder=10, label=label)
            if self.petro_markers.isChecked():
                scatter_kw['marker'] = g['marker']
            sc = ax.scatter(g['xs'], g['ys'], **scatter_kw)
            artist_registry.setdefault(g['name'], []).append({'artist': sc, 'role': 'scatter'})
            for local_idx, fid in enumerate(g['fids']):
                fid_to_scatter[fid] = (sc, local_idx)

        ax.set_xlabel(f"{x_field}{x_unit_label}", fontsize=12)
        ax.set_ylabel(f"{y_field}{y_unit_label}", fontsize=12)
        ax.set_title(f"{y_field} vs {x_field} (n={valid_count})", fontsize=14)
        ax.grid(True, alpha=0.3)

        export_legend_artists = {}
        category_legend_obj = None
        if self.petro_legend.isChecked() and unique_categories:
            export_legend_artists = self._build_category_legend(
                ax, unique_categories, category_styles, Counter(sample_names),
                bbox_to_anchor=(0.5, -0.12), fontsize=8)
            category_legend_obj = ax.get_legend()

        if bubble_active:
            self._add_bubble_size_legend(
                ax, bubble_vmin, bubble_vmax, bubble_min_size, bubble_max_size, bubble_method,
                self._field_display_label(size_field), category_legend_obj)

        plt.tight_layout()
        fig.subplots_adjust(bottom=0.2)
        plt.show()
        self._attach_scatter_selection(fig, ax, pts_data, fid_list, fid_to_scatter, layer.id())
        self._open_category_panel(
            fig, artist_registry, category_counts=Counter(sample_names), category_styles=category_styles,
            style_template_key=self._category_field_label(), export_legend_artists=export_legend_artists,
            title='Petrophysics Categories', bubble_active=bubble_active)
        self.current_fig = fig

    def _apply_bdl_substitution(self, value):
        """Substitute a below-detection-limit code (a negative value) with a
        positive proxy, per the Custom XY tab's Data Preprocessing settings.

        Returns `value` unchanged if it's None, non-negative, or the
        "Treat negative values..." checkbox is off - i.e. by default
        negative values pass through untouched rather than being discarded,
        so plots can show them as literal (negative) numbers if desired.
        """
        if value is None or value >= 0:
            return value
        if not self.custom_bdl_enabled.isChecked():
            return value
        detection_limit = abs(value)
        method = self.custom_bdl_method_combo.currentText()
        if method == 'Half of detection limit':
            return detection_limit / 2.0
        if method == 'Detection limit':
            return detection_limit
        if method == 'Random value (0 to detection limit)':
            return random.uniform(0.0, detection_limit)
        if method == 'Fixed value':
            return self.custom_bdl_fixed_spin.value()
        return value

    def _review_custom_xy_negatives(self):
        """Summarise negative (below-detection-limit-coded) values found in
        the currently selected samples, for the X/Y fields chosen in the
        Plot Setup sub-tab, and plot a histogram of their magnitudes
        (i.e. the encoded detection limits) to help choose a substitution.
        """
        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            QMessageBox.warning(self, "Warning", "Please select a valid layer.")
            return

        selected_items = self.feature_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select at least one sample.")
            return
        features = [layer.getFeature(item.data(Qt_UserRole)) for item in selected_items]

        fields = [f for f in dict.fromkeys([
            self.x_num_combo.currentText(), self.x_denom_combo.currentText(),
            self.y_num_combo.currentText(), self.y_denom_combo.currentText(),
        ]) if f not in ('1 (none)', 'Mg#')]

        if not fields:
            self.custom_bdl_review_label.setText("No fields selected to review.")
            return

        summary_lines = []
        detection_limits_by_field = {}
        for field in fields:
            values = [get_custom_element_value(feature, layer, field) for feature in features]
            negatives = [v for v in values if v is not None and v < 0]
            if negatives:
                dls = [abs(v) for v in negatives]
                summary_lines.append(
                    f"{field}: {len(negatives)} of {len(features)} sample(s) negative, "
                    f"detection limit range {min(dls):.4g}–{max(dls):.4g}")
                detection_limits_by_field[field] = dls
            else:
                summary_lines.append(f"{field}: no negative values found")

        self.custom_bdl_review_label.setText("\n".join(summary_lines))
        self.custom_bdl_review_label.setStyleSheet("color: black;")

        if detection_limits_by_field:
            fig, ax = plt.subplots(figsize=(8, 5))
            for field, dls in detection_limits_by_field.items():
                ax.hist(dls, bins=min(20, max(5, len(dls))), alpha=0.6, label=field, edgecolor='black')
            ax.set_xlabel("Detection limit (|value|)")
            ax.set_ylabel("Sample count")
            ax.set_title("Detection limits encoded by negative values")
            ax.legend()
            plt.tight_layout()
            plt.show()

    def generate_custom_xy_plot(self, layer, features, sample_names):
        """Generate custom XY plot."""
        x_num = self.x_num_combo.currentText()
        x_denom = self.x_denom_combo.currentText()
        y_num = self.y_num_combo.currentText()
        y_denom = self.y_denom_combo.currentText()
        size_field, bubble_active, bubble_min_size, bubble_max_size, bubble_method = \
            self._read_bubble_controls('custom')

        ree_norm_id = self.ree_norm_combo.currentIndex()
        norm_values = None
        norm_name = ""
        if ree_norm_id > 0:
            try:
                norm_name, norm_values = NORMALIZATION_OPTIONS[ree_norm_id - 1]
            except IndexError:
                norm_values = None
                norm_name = ""
        
        def build_label(num, denom, norm_values):
            num_is_ree = num in REE_ELEMENTS
            denom_is_ree = denom in REE_ELEMENTS if denom != '1 (none)' else False
            
            norm_suffix = ""
            if norm_values:
                if num_is_ree or denom_is_ree:
                    norm_suffix = "ₙ"
            
            def get_unit(elem):
                # A field picked via "show all numeric fields" isn't a
                # recognised symbol - its raw name already carries its own
                # unit (e.g. "S_ppm"), so don't add a redundant suffix.
                if elem not in CUSTOM_XY_ELEMENTS:
                    return ''
                if elem in ('1 (none)', 'Mg#'):
                    return ''
                if elem in OXIDE_COMPOSITION:
                    return ' (wt%)'
                return ' (ppm)'
            
            if denom == '1 (none)':
                unit = get_unit(num)
                if norm_suffix and num_is_ree:
                    return f"{num}{norm_suffix}{unit}"
                return f"{num}{unit}"
            else:
                num_str = f"{num}{norm_suffix}" if norm_suffix and num_is_ree else num
                denom_str = f"{denom}{norm_suffix}" if norm_suffix and denom_is_ree else denom
                return f"{num_str} / {denom_str}"
        
        x_label = build_label(x_num, x_denom, norm_values)
        y_label = build_label(y_num, y_denom, norm_values)
        
        # Check required elements
        elements_needed = set()
        for elem in [x_num, x_denom, y_num, y_denom] + ([size_field] if bubble_active else []):
            if elem != '1 (none)':
                if elem == 'Mg#':
                    elements_needed.add('MgO')
                    elements_needed.add('FeO')
                else:
                    elements_needed.add(elem)
        
        missing_elements = []
        for elem in sorted(elements_needed):
            field = find_element_field(layer, elem)
            if field is None:
                missing_elements.append(elem)
        
        if missing_elements:
            QMessageBox.warning(self, "Warning", 
                f"Missing elements: {', '.join(missing_elements)}\nPlot cannot be generated.")
            return
        
        x_data = []
        y_data = []
        size_data = []
        valid_count = 0

        for feature in features:
            # Negative values (commonly used to code "below detection
            # limit" in exploration datasets) are substituted per the Data
            # Preprocessing tab if enabled, otherwise passed through as
            # literal negative numbers rather than being discarded.
            x_num_val = self._apply_bdl_substitution(get_custom_element_value(
                feature, layer, x_num,
                normalize=(norm_values is not None and x_num in REE_ELEMENTS),
                norm_values=norm_values))
            x_denom_val = self._apply_bdl_substitution(get_custom_element_value(
                feature, layer, x_denom,
                normalize=(norm_values is not None and x_denom in REE_ELEMENTS),
                norm_values=norm_values))

            y_num_val = self._apply_bdl_substitution(get_custom_element_value(
                feature, layer, y_num,
                normalize=(norm_values is not None and y_num in REE_ELEMENTS),
                norm_values=norm_values))
            y_denom_val = self._apply_bdl_substitution(get_custom_element_value(
                feature, layer, y_denom,
                normalize=(norm_values is not None and y_denom in REE_ELEMENTS),
                norm_values=norm_values))

            x_val = None
            y_val = None

            if x_num_val is not None and x_denom_val:
                x_val = x_num_val / x_denom_val

            if y_num_val is not None and y_denom_val:
                y_val = y_num_val / y_denom_val

            x_data.append(x_val)
            y_data.append(y_val)
            size_val = self._apply_bdl_substitution(
                get_custom_element_value(feature, layer, size_field)) if bubble_active else None
            size_data.append(size_val)

            if x_val is not None and y_val is not None:
                valid_count += 1

        if valid_count == 0:
            QMessageBox.warning(self, "Warning", "No valid data points to plot.")
            return

        # Compute the data range that will drive bubble sizing, from points
        # that will actually be plotted (valid x and y). Log10 scaling needs
        # strictly positive values, so those are excluded from the range
        # (individual non-positive points still plot, at bubble_min_size).
        valid_mask = [x is not None and y is not None for x, y in zip(x_data, y_data)]
        bubble_vmin = bubble_vmax = None
        if bubble_active:
            bubble_vmin, bubble_vmax, bubble_active = self._compute_bubble_range(
                'custom', size_data, valid_mask, bubble_method)

        category_styles, unique_categories = self._build_default_category_styles(sample_names)
        category_colors, category_markers, sample_colors, sample_markers = \
            self._category_arrays_from_styles(category_styles, sample_names)

        fig, ax = plt.subplots(figsize=(12, 9))

        if self.x_scale_combo.currentIndex() == 1:
            ax.set_xscale('log')
        if self.y_scale_combo.currentIndex() == 1:
            ax.set_yscale('log')

        default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        plotted_categories = set()
        pts_data = []
        fid_list = []
        fid_to_scatter = {}  # fid -> (PathCollection, local_index within that collection)
        artist_registry = {}

        # Group points by category so we make one ax.scatter() call per group instead
        # of one per point, eliminating the O(n_points) PathCollection overhead.
        cat_groups = {}
        for i, (x, y, name, feature) in enumerate(zip(x_data, y_data, sample_names, features)):
            if x is not None and y is not None:
                color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
                marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
                cat_key = (name, marker) if self.custom_markers.isChecked() else name
                if cat_key not in cat_groups:
                    cat_groups[cat_key] = {'xs': [], 'ys': [], 'fids': [], 'colors': [], 'sizes': [],
                                           'marker': marker, 'name': name}
                g = cat_groups[cat_key]
                g['xs'].append(x)
                g['ys'].append(y)
                g['fids'].append(feature.id())
                g['colors'].append(color)
                if bubble_active:
                    sv = size_data[i]
                    size = (bubble_symbol_size(sv, bubble_vmin, bubble_vmax, bubble_min_size,
                                               bubble_max_size, bubble_method)
                            if sv is not None else bubble_min_size)
                else:
                    size = 80
                g['sizes'].append(size)
                pts_data.append((x, y))
                fid_list.append(feature.id())

        for cat_key, g in cat_groups.items():
            label = None
            if self.custom_legend.isChecked() and g['name'] not in plotted_categories:
                label = g['name']
                plotted_categories.add(g['name'])
            scatter_kw = dict(s=g['sizes'], c=g['colors'], edgecolors='black',
                              linewidths=0.5, zorder=10, label=label)
            if self.custom_markers.isChecked():
                scatter_kw['marker'] = g['marker']
            sc = ax.scatter(g['xs'], g['ys'], **scatter_kw)
            artist_registry.setdefault(g['name'], []).append({'artist': sc, 'role': 'scatter'})
            for local_idx, fid in enumerate(g['fids']):
                fid_to_scatter[fid] = (sc, local_idx)

        ax.set_xlabel(x_label, fontsize=12)
        ax.set_ylabel(y_label, fontsize=12)

        title = f"{y_label} vs {x_label} (n={valid_count})"
        if norm_values:
            title += f"\nREE normalized to {norm_name}"
        ax.set_title(title, fontsize=14)

        ax.grid(True, alpha=0.3)

        export_legend_artists = {}
        category_legend_obj = None
        if self.custom_legend.isChecked() and len(unique_categories) > 0:
            export_legend_artists = self._build_category_legend(
                ax, unique_categories, category_styles, Counter(sample_names),
                bbox_to_anchor=(0.5, -0.12), fontsize=8)
            category_legend_obj = ax.get_legend()

        if bubble_active:
            self._add_bubble_size_legend(
                ax, bubble_vmin, bubble_vmax, bubble_min_size, bubble_max_size, bubble_method,
                build_label(size_field, '1 (none)', None), category_legend_obj)

        plt.tight_layout()
        fig.subplots_adjust(bottom=0.2)
        plt.show()
        self._attach_scatter_selection(fig, ax, pts_data, fid_list, fid_to_scatter, layer.id())
        self._open_category_panel(
            fig, artist_registry, category_counts=Counter(sample_names), category_styles=category_styles,
            style_template_key=self._category_field_label(), export_legend_artists=export_legend_artists,
            title='Custom XY Plot Categories', bubble_active=bubble_active)
        self.current_fig = fig

    def _attach_scatter_selection(self, fig, ax, pts_data, fid_list, fid_to_scatter, layer_id):
        """Wire up point selection on scatter-based plots.

        Left-click (no toolbar mode): select nearest point in QGIS.
        Shift+left-click: toggle that point in the QGIS selection.
        Left-click on empty space: clear QGIS selection.
        Left-drag: rubber-band rectangle selects all enclosed points.
        Shift+left-drag: adds enclosed points to the current selection.
        Selected points are highlighted with a red edge on the plot.
        """
        if not pts_data or not fid_list:
            return

        pts_array = np.array(pts_data, dtype=float)
        fid_to_pt = dict(zip(fid_list, pts_data))
        current_labels = []

        # Hover tooltip annotation (hidden until mouse is near a point)
        hover_ann = ax.annotate(
            '', xy=(0, 0), xytext=(10, 10), textcoords='offset points',
            bbox=dict(boxstyle='round,pad=0.3', fc='lightyellow', ec='gray', alpha=0.9),
            fontsize=8, visible=False, zorder=20
        )

        def apply_selection(selected_fids):
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer is None:
                return
            layer.selectByIds(selected_fids)
            selected_set = set(selected_fids)

            for ann in current_labels:
                try:
                    ann.remove()
                except Exception:
                    pass
            current_labels.clear()

            # Batch colour update — one set_edgecolors() call per collection, not per point.
            coll_edge = {}
            coll_lw   = {}
            for fid, (sc, local_idx) in fid_to_scatter.items():
                if sc not in coll_edge:
                    n = len(sc.get_offsets())
                    coll_edge[sc] = ['black'] * n
                    coll_lw[sc]   = [0.5] * n
                if fid in selected_set:
                    coll_edge[sc][local_idx] = 'red'
                    coll_lw[sc][local_idx]   = 2.0
            for sc in coll_edge:
                sc.set_edgecolors(coll_edge[sc])
                sc.set_linewidths(coll_lw[sc])

            if self.discrim_label.isChecked() and selected_fids:
                label_field = self.label_field_combo.currentText()
                layer_field_names = [f.name() for f in layer.fields()]
                if label_field in layer_field_names:
                    for fid in selected_fids:
                        if fid not in fid_to_pt:
                            continue
                        x, y = fid_to_pt[fid]
                        feature = layer.getFeature(fid)
                        if not feature.isValid():
                            continue
                        val = feature[label_field]
                        if val is not None and val != NULL:
                            # zorder=20 matches the hover tooltip so labels
                            # always render above the scatter points (zorder=10)
                            # instead of being hidden behind them. The white
                            # bbox masks whatever is underneath so the text
                            # stays legible over busy plot areas.
                            ann = ax.annotate(
                                str(val), xy=(x, y),
                                xytext=(6, 0), textcoords='offset points',
                                fontsize=8, va='center', zorder=20,
                                bbox=dict(boxstyle='round,pad=0.15', fc='white',
                                         ec='none', alpha=0.75)
                            )
                            current_labels.append(ann)

            fig.canvas.draw_idle()
            self.refresh_selection()

        # Ensure selected features always render on top of unselected ones in QGIS.
        # Sorts by is_selected() ascending (0 = unselected first, 1 = selected last/on top).
        _layer_init = QgsProject.instance().mapLayer(layer_id)
        if _layer_init is not None:
            try:
                from qgis.core import QgsFeatureRequest
                renderer = _layer_init.renderer()
                if renderer is not None:
                    order_by = QgsFeatureRequest.OrderBy([
                        QgsFeatureRequest.OrderByClause('is_selected()', ascending=True, nullsfirst=False)
                    ])
                    renderer.setOrderBy(order_by)
                    renderer.setOrderByEnabled(True)
                    _layer_init.triggerRepaint()
            except Exception:
                pass

        _rect_used = [False]

        def on_rect_select(eclick, erelease):
            if eclick.xdata is None or erelease.xdata is None:
                return
            try:
                p1 = ax.transData.transform([[eclick.xdata, eclick.ydata]])[0]
                p2 = ax.transData.transform([[erelease.xdata, erelease.ydata]])[0]
                if np.linalg.norm(p2 - p1) < 5:
                    return
            except Exception:
                return
            _rect_used[0] = True
            x1 = min(eclick.xdata, erelease.xdata)
            x2 = max(eclick.xdata, erelease.xdata)
            y1 = min(eclick.ydata, erelease.ydata)
            y2 = max(eclick.ydata, erelease.ydata)
            xs = pts_array[:, 0]
            ys = pts_array[:, 1]
            inside = (xs >= x1) & (xs <= x2) & (ys >= y1) & (ys <= y2)
            new_fids = [fid_list[i] for i, flag in enumerate(inside) if flag]
            key = eclick.key or ''
            if 'shift' in key.lower():
                layer = QgsProject.instance().mapLayer(layer_id)
                if layer is not None:
                    current = set(layer.selectedFeatureIds())
                    current.update(new_fids)
                    new_fids = list(current)
            apply_selection(new_fids)
            fig.canvas.draw_idle()

        def on_click(event):
            if event.button != 1:
                return
            # If rectangle select just fired on this mouse-up, skip single-point logic
            if _rect_used[0]:
                _rect_used[0] = False
                return
            try:
                if fig.canvas.toolbar.mode != '':
                    return
            except AttributeError:
                pass
            if event.inaxes is None or event.xdata is None or event.ydata is None:
                return

            layer = QgsProject.instance().mapLayer(layer_id)
            if layer is None:
                return

            try:
                pts_disp = ax.transData.transform(pts_array)
                click_disp = ax.transData.transform([[event.xdata, event.ydata]])[0]
            except Exception:
                return

            dists = np.sqrt(np.sum((pts_disp - click_disp) ** 2, axis=1))
            nearest_idx = int(np.argmin(dists))
            key = event.key or ''

            if dists[nearest_idx] > 10:
                if 'shift' not in key.lower():
                    apply_selection([])
                return

            fid = fid_list[nearest_idx]
            if 'shift' in key.lower():
                current = set(layer.selectedFeatureIds())
                current.symmetric_difference_update({fid})
                apply_selection(list(current))
            else:
                apply_selection([fid])

        _hover_cache = {}   # (fid, field_name) → label string
        _last_hover_fid = [None]

        def on_hover(event):
            if event.inaxes != ax or event.xdata is None:
                if hover_ann.get_visible():
                    hover_ann.set_visible(False)
                    fig.canvas.draw_idle()
                _last_hover_fid[0] = None
                return
            try:
                pts_disp = ax.transData.transform(pts_array)
                cur_disp = ax.transData.transform([[event.xdata, event.ydata]])[0]
            except Exception:
                return
            dists = np.sqrt(np.sum((pts_disp - cur_disp) ** 2, axis=1))
            nearest_idx = int(np.argmin(dists))
            if dists[nearest_idx] <= 10:
                fid = fid_list[nearest_idx]
                label_field = self.label_field_combo.currentText()
                cache_key = (fid, label_field)
                if cache_key not in _hover_cache:
                    layer = QgsProject.instance().mapLayer(layer_id)
                    val = ''
                    if layer and label_field in [f.name() for f in layer.fields()]:
                        feat = layer.getFeature(fid)
                        if feat.isValid():
                            v = feat[label_field]
                            val = str(v) if v is not None and v != NULL else ''
                    _hover_cache[cache_key] = val
                label = _hover_cache[cache_key]
                if fid != _last_hover_fid[0]:
                    _last_hover_fid[0] = fid
                    if label:
                        hover_ann.set_text(label)
                        hover_ann.xy = pts_data[nearest_idx]
                        hover_ann.set_visible(True)
                    else:
                        hover_ann.set_visible(False)
                    fig.canvas.draw_idle()
            else:
                if _last_hover_fid[0] is not None:
                    _last_hover_fid[0] = None
                    hover_ann.set_visible(False)
                    fig.canvas.draw_idle()

        fig.canvas.mpl_connect('button_release_event', on_click)
        fig.canvas.mpl_connect('motion_notify_event', on_hover)
        rect = RectangleSelector(ax, on_rect_select, useblit=True, button=[1],
                                 props=dict(edgecolor='steelblue', facecolor='lightsteelblue',
                                            alpha=0.3, linewidth=1.5))
        fig._rect_selector = rect  # keep reference so it isn't garbage-collected

    def _attach_spider_selection(self, fig, line_to_fid, layer_id):
        """Wire up click-to-select on spider diagram lines.

        Click on a line: select that sample in QGIS.
        Shift+click: toggle that sample in the QGIS selection.
        Selected lines are drawn bold; unselected lines are dimmed.
        """
        if not line_to_fid:
            return

        fid_to_line = {fid: line for line, fid in line_to_fid.items()}

        for line in line_to_fid:
            line.set_picker(5)

        def apply_selection(selected_fids):
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer is None:
                return
            layer.selectByIds(selected_fids)
            selected_set = set(selected_fids)
            for fid, line in fid_to_line.items():
                if fid in selected_set:
                    line.set_linewidth(3.0)
                    line.set_alpha(1.0)
                    line.set_zorder(10)
                else:
                    line.set_linewidth(1.5)
                    line.set_alpha(0.35)
                    line.set_zorder(5)
            fig.canvas.draw_idle()
            self.refresh_selection()

        def on_pick(event):
            if not isinstance(event.artist, Line2D):
                return
            if event.artist not in line_to_fid:
                return
            try:
                if fig.canvas.toolbar.mode != '':
                    return
            except AttributeError:
                pass

            layer = QgsProject.instance().mapLayer(layer_id)
            if layer is None:
                return

            fid = line_to_fid[event.artist]
            key = getattr(event.mouseevent, 'key', None) or ''
            if 'shift' in key.lower():
                current = set(layer.selectedFeatureIds())
                current.symmetric_difference_update({fid})
                apply_selection(list(current))
            else:
                apply_selection([fid])

        ax = next(iter(line_to_fid)).axes
        hover_ann = ax.annotate(
            '', xy=(0, 0), xytext=(10, 10), textcoords='offset points',
            bbox=dict(boxstyle='round,pad=0.3', fc='lightyellow', ec='gray', alpha=0.9),
            fontsize=8, visible=False, zorder=20
        )
        _hover_cache = {}   # (fid, field_name) → label string
        _last_hover_fid = [None]

        def on_hover(event):
            if event.inaxes != ax or event.xdata is None:
                if hover_ann.get_visible():
                    hover_ann.set_visible(False)
                    fig.canvas.draw_idle()
                _last_hover_fid[0] = None
                return
            hit_fid = None
            for line, fid in line_to_fid.items():
                contains, _ = line.contains(event)
                if contains:
                    hit_fid = fid
                    break
            if hit_fid is not None:
                label_field = self.label_field_combo.currentText()
                cache_key = (hit_fid, label_field)
                if cache_key not in _hover_cache:
                    layer = QgsProject.instance().mapLayer(layer_id)
                    val = ''
                    if layer and label_field in [f.name() for f in layer.fields()]:
                        feat = layer.getFeature(hit_fid)
                        if feat.isValid():
                            v = feat[label_field]
                            val = str(v) if v is not None and v != NULL else ''
                    _hover_cache[cache_key] = val
                label = _hover_cache[cache_key]
                if hit_fid != _last_hover_fid[0]:
                    _last_hover_fid[0] = hit_fid
                    if label:
                        hover_ann.set_text(label)
                        hover_ann.xy = (event.xdata, event.ydata)
                        hover_ann.set_visible(True)
                    else:
                        hover_ann.set_visible(False)
                    fig.canvas.draw_idle()
            else:
                if _last_hover_fid[0] is not None:
                    _last_hover_fid[0] = None
                    hover_ann.set_visible(False)
                    fig.canvas.draw_idle()

        fig.canvas.mpl_connect('pick_event', on_pick)
        fig.canvas.mpl_connect('motion_notify_event', on_hover)

    # ------------------------------------------------------------------
    # Interactive category styling (colour / marker / size / legend panel)
    # ------------------------------------------------------------------

    def _default_category_style(self, index, color=None, marker=None):
        """Return a default style dict for a category.

        When color/marker are supplied (typically from the auto colour map)
        they are used as-is; otherwise a fixed fallback palette is used, e.g.
        when resetting a category style back to its default.
        """
        palette = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple',
                   'tab:brown', 'tab:pink', 'tab:gray', 'tab:olive', 'tab:cyan']
        markers = [m for _, m in STYLE_MARKER_OPTIONS]
        if color is None:
            color = palette[index % len(palette)]
        if marker is None:
            marker = markers[index % len(markers)]
        return {
            'color': mcolors.to_hex(color),
            'marker': marker,
            'markersize': 8.0,
            'linewidth': 1.5,
            'alpha': 1.0,
        }

    def _style_templates_path(self):
        """Return the project-level JSON file used for category style templates."""
        project_file = QgsProject.instance().fileName()
        if project_file:
            config_dir = os.path.join(
                os.path.dirname(os.path.abspath(project_file)), '99_COMMAND_FILES_PLUGIN')
            return os.path.join(config_dir, 'geochem_plot_styles.json')
        return os.path.join(os.path.expanduser('~'), 'geochem_plot_styles.json')

    def _load_style_templates(self):
        """Load saved category style templates from JSON."""
        path = self._style_templates_path()
        if not path or not os.path.exists(path):
            return {'version': 1, 'templates': {}}
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except Exception:
            return {'version': 1, 'templates': {}}
        if not isinstance(data, dict):
            return {'version': 1, 'templates': {}}
        data.setdefault('version', 1)
        data.setdefault('templates', {})
        if not isinstance(data['templates'], dict):
            data['templates'] = {}
        return data

    def _save_style_templates(self, data):
        """Persist category style templates to JSON."""
        path = self._style_templates_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
        return path

    def _normalise_category_style(self, style, fallback_index=0):
        """Return a complete, JSON-safe category style dictionary."""
        fallback = self._default_category_style(fallback_index)
        if not isinstance(style, dict):
            style = {}
        result = dict(fallback)
        result.update({k: v for k, v in style.items() if k in result})
        for key in ('markersize', 'linewidth', 'alpha'):
            try:
                result[key] = float(result.get(key, fallback[key]))
            except Exception:
                result[key] = float(fallback[key])
        result['alpha'] = max(0.05, min(1.0, result['alpha']))
        for key in ('color', 'marker'):
            result[key] = str(result.get(key, fallback[key]))
        return result

    def _set_artist_visible(self, artist, visible):
        """Set visibility on a Matplotlib artist, or a dict/list of artists."""
        if artist is None:
            return
        if isinstance(artist, dict):
            return self._set_artist_visible(artist.get('artist'), visible)
        if isinstance(artist, (list, tuple)):
            for item in artist:
                self._set_artist_visible(item, visible)
            return
        if hasattr(artist, 'set_visible'):
            artist.set_visible(visible)

    def _build_default_category_styles(self, sample_names):
        """Build fresh default per-category styles seeded from the auto colour map."""
        category_colors, _, unique_categories, category_markers, _ = create_categorical_color_map(sample_names)
        category_styles = {
            cat: self._default_category_style(i, color=category_colors[cat], marker=category_markers[cat])
            for i, cat in enumerate(unique_categories)
        }
        return category_styles, unique_categories

    def _category_arrays_from_styles(self, category_styles, sample_names):
        """Expand a {category: style} dict into the flat colour/marker arrays plotting code expects."""
        category_colors = {cat: mcolors.to_rgba(style['color']) for cat, style in category_styles.items()}
        category_markers = {cat: style['marker'] for cat, style in category_styles.items()}
        sample_colors = [category_colors[n] for n in sample_names]
        sample_markers = [category_markers[n] for n in sample_names]
        return category_colors, category_markers, sample_colors, sample_markers

    def _extract_legend_artists(self, legend):
        """Return {category: [{'artist':handle,'role':...}, {'artist':text,'role':'legend_label'}]}
        for an existing Matplotlib legend, so it can be kept in sync with live style edits.
        """
        export_legend_artists = {}
        if legend is None:
            return export_legend_artists
        handles = getattr(legend, 'legend_handles', None)
        if handles is None:
            handles = getattr(legend, 'legendHandles', [])
        for handle, text in zip(handles, legend.get_texts()):
            # Legend labels may carry a " (n=123)" count suffix; strip it to
            # recover the raw category name used as the artist_registry key.
            category = re.sub(r'\s*\(n=\d+\)$', '', text.get_text())
            text.set_color('black')
            role = 'scatter' if hasattr(handle, 'set_paths') else 'marker'
            export_legend_artists.setdefault(category, []).extend([
                {'artist': handle, 'role': role},
                {'artist': text, 'role': 'legend_label'},
            ])
        return export_legend_artists

    def _build_category_legend(self, ax, category_values, category_styles, category_counts,
                               bbox_to_anchor=(0.5, -0.12), fontsize=8):
        """Draw an explicit per-category legend and return its restylable artists.

        Building the legend from category_styles directly (rather than letting
        Matplotlib auto-generate it from plotted artists) means every category
        gets exactly one legend entry, styled consistently, even when a
        category is split across several point groups (e.g. mixed markers).
        """
        if not category_values:
            return {}
        n_categories = len(category_values)
        ncol = max(1, min(6, (n_categories + 3) // 4))
        legend_handles = []
        legend_labels = []
        for cat in category_values:
            style = category_styles.get(cat, self._default_category_style(0))
            legend_handles.append(Line2D(
                [0], [0], linestyle='none',
                marker=style.get('marker', 'o'),
                markerfacecolor=style.get('color', '#000000'),
                markeredgecolor=style.get('color', '#000000'),
                markersize=max(4.0, float(style.get('markersize', 8)) * 0.7),
                alpha=float(style.get('alpha', 1.0))))
            legend_labels.append(f"{cat} (n={category_counts.get(cat, 0)})")
        ax.legend(legend_handles, legend_labels, loc='upper center',
                 bbox_to_anchor=bbox_to_anchor, fontsize=fontsize,
                 ncol=ncol, framealpha=0.9, borderaxespad=0.)
        return self._extract_legend_artists(ax.get_legend())

    def _field_display_label(self, field):
        """Human-readable label for a single element/oxide field, with unit."""
        if field in OXIDE_COMPOSITION:
            return f"{field} (wt%)"
        if field in CUSTOM_XY_ELEMENTS and field not in ('1 (none)', 'Mg#'):
            return f"{field} (ppm)"
        return field

    def _add_bubble_size_legend(self, ax, vmin, vmax, min_size, max_size, method, label,
                                category_legend_obj=None):
        """Draw a small reference-bubble legend (min/mid/max value -> size) on
        `ax`, so the size-to-value mapping is readable directly off the plot.

        Building a legend replaces any legend already on the axes, so a
        previously-built category legend must be passed in as
        `category_legend_obj` (its `ax.get_legend()` return value) to be
        re-added via `ax.add_artist()` and shown alongside this one.
        """
        mid_value = math.sqrt(vmin * vmax) if vmin > 0 and vmax > 0 else (vmin + vmax) / 2.0
        legend_values = sorted(set([vmin, mid_value, vmax]))
        size_handles = [
            ax.scatter([], [], s=bubble_symbol_size(v, vmin, vmax, min_size, max_size, method),
                      facecolors='none', edgecolors='black', linewidths=1.0)
            for v in legend_values
        ]
        size_labels = [f'{v:.3g}' for v in legend_values]
        ax.legend(size_handles, size_labels, title=label, loc='upper left', fontsize=8,
                 title_fontsize=9, framealpha=0.9, labelspacing=1.4, borderpad=1.1,
                 handletextpad=1.2)
        if category_legend_obj is not None:
            ax.add_artist(category_legend_obj)

    def _apply_style_to_matplotlib_artist(self, artist, role, style, lock_size=False):
        """Push a category style dict onto a single plotted or legend artist.

        `lock_size=True` leaves marker/point sizes untouched - used when a
        plot has bubble sizing active, so restyling a category's colour,
        marker shape or transparency never flattens its per-point sizes.
        """
        if artist is None:
            return
        if isinstance(artist, dict):
            return self._apply_style_to_matplotlib_artist(
                artist.get('artist'), artist.get('role', role), style, lock_size=lock_size)
        if isinstance(artist, (list, tuple)):
            for item in artist:
                self._apply_style_to_matplotlib_artist(item, role, style, lock_size=lock_size)
            return

        alpha = float(style.get('alpha', 1.0))
        colour = style.get('color', '#000000')
        line_width = float(style.get('linewidth', 1.0))

        if role == 'legend_label':
            # Legend text stays plain black; only the marker swatch restyles.
            return
        if role == 'scatter':
            # PathCollection (ax.scatter and its legend handle). The black
            # point outline is left untouched since it also doubles as the
            # QGIS-selection highlight colour (see _attach_scatter_selection).
            if hasattr(artist, 'set_facecolor'):
                artist.set_facecolor(colour)
            if not lock_size and hasattr(artist, 'set_sizes'):
                n = max(1, len(artist.get_offsets()))
                artist.set_sizes([float(style.get('markersize', 8)) ** 2] * n)
            if hasattr(artist, 'set_paths'):
                try:
                    ms = MarkerStyle(style.get('marker', 'o'))
                    artist.set_paths([ms.get_path().transformed(ms.get_transform())])
                except Exception:
                    pass
            if hasattr(artist, 'set_alpha'):
                artist.set_alpha(alpha)
        else:
            # Line2D (spider-diagram sample lines and their legend handles).
            if hasattr(artist, 'set_marker'):
                artist.set_marker(style.get('marker', 'o'))
            if not lock_size and hasattr(artist, 'set_markersize'):
                artist.set_markersize(float(style.get('markersize', 8)))
            if hasattr(artist, 'set_markerfacecolor'):
                artist.set_markerfacecolor(colour)
            if hasattr(artist, 'set_markeredgecolor'):
                artist.set_markeredgecolor(colour)
            if hasattr(artist, 'set_color'):
                artist.set_color(colour)
            if hasattr(artist, 'set_linewidth'):
                artist.set_linewidth(line_width)
            if hasattr(artist, 'set_alpha'):
                artist.set_alpha(alpha)

    def _open_category_panel(self, fig, artist_registry, category_counts=None,
                             category_styles=None, title='Plot Categories',
                             style_template_key=None, export_legend_artists=None,
                             bubble_active=False):
        """Embed category visibility/style controls in a right-hand Qt panel.

        The panel is attached to the Matplotlib figure's own Qt window as a
        dock, so it never overlaps the plot axes and keeps working when the
        plot window is resized. Falls back to on-axes CheckButtons/Button
        widgets for non-Qt Matplotlib backends.

        `bubble_active=True` disables per-category symbol-size editing here,
        since the plot's marker sizes are already driven by its bubble-size
        scaling and would otherwise be silently flattened by this panel.
        """
        if not artist_registry:
            return

        category_counts = category_counts or {}
        category_styles = category_styles or {}
        export_legend_artists = export_legend_artists or {}
        categories = sorted(artist_registry.keys(), key=lambda x: str(x))
        visible_state = {category: True for category in categories}

        def _apply_category_style(category):
            style = category_styles.get(category, self._default_category_style(0))
            for entry in artist_registry.get(category, []):
                self._apply_style_to_matplotlib_artist(entry, 'marker', style, lock_size=bubble_active)
            for legend_artist in export_legend_artists.get(category, []):
                self._apply_style_to_matplotlib_artist(legend_artist, 'marker', style, lock_size=bubble_active)
            fig.canvas.draw_idle()

        def _sync_legend_symbols():
            for category in categories:
                style = category_styles.get(category, self._default_category_style(0))
                if category in legend_symbol_by_category:
                    legend_symbol_by_category[category].set_symbol_style(
                        style.get('marker', 'o'), style.get('color', '#000000'))
                    legend_symbol_by_category[category].setToolTip(
                        f"{style.get('marker', 'o')} / {style.get('color', '#000000')}")

        def _refresh_category_visibility():
            for category, visible in visible_state.items():
                for artist in artist_registry.get(category, []):
                    self._set_artist_visible(artist, visible)
                for legend_artist in export_legend_artists.get(category, []):
                    self._set_artist_visible(legend_artist, visible)
            fig.canvas.draw_idle()

        def _apply_all_category_styles():
            for category in categories:
                _apply_category_style(category)
            _sync_legend_symbols()
            _refresh_category_visibility()

        manager = getattr(fig.canvas, 'manager', None)
        window = getattr(manager, 'window', None)

        # Preferred path: a native Qt dock on the right of the Matplotlib window.
        if window is not None and hasattr(window, 'addDockWidget'):
            dock = QDockWidget(title, window)
            dock.setObjectName('GeochemCategoryDock')
            dock.setAllowedAreas(LeftDockWidgetArea | RightDockWidgetArea)

            panel = QWidget(dock)
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(8, 8, 8, 8)
            panel_layout.setSpacing(6)

            style_mgmt_group = QGroupBox('Style Management', panel)
            style_mgmt_layout = QVBoxLayout(style_mgmt_group)
            style_mgmt_caption = QLabel(
                'Save, load, reset or delete reusable category style templates.', style_mgmt_group)
            style_mgmt_caption.setWordWrap(True)
            style_mgmt_layout.addWidget(style_mgmt_caption)

            template_row = QHBoxLayout()
            save_template_btn = QPushButton('Save')
            load_template_btn = QPushButton('Load')
            reset_styles_btn = QPushButton('Reset')
            delete_template_btn = QPushButton('Delete')
            save_template_btn.setToolTip('Save the current category styles as a reusable template.')
            load_template_btn.setToolTip('Load a previously saved category style template.')
            reset_styles_btn.setToolTip('Reset category styles to the default palette and markers.')
            delete_template_btn.setToolTip('Delete an existing saved category style template.')
            for btn in (save_template_btn, load_template_btn, reset_styles_btn, delete_template_btn):
                template_row.addWidget(btn)
            style_mgmt_layout.addLayout(template_row)
            panel_layout.addWidget(style_mgmt_group, 0)

            class_group = QGroupBox('Categories', panel)
            class_layout = QVBoxLayout(class_group)
            caption = QLabel('Toggle category visibility, or edit its colour, marker, size and transparency.')
            caption.setWordWrap(True)
            class_layout.addWidget(caption)

            button_row = QHBoxLayout()
            show_btn = QPushButton('All')
            hide_btn = QPushButton('None')
            invert_btn = QPushButton('Invert')
            for btn in (show_btn, hide_btn, invert_btn):
                button_row.addWidget(btn)
            class_layout.addLayout(button_row)

            checkbox_by_category = {}
            controls_widget = QWidget(panel)
            controls_layout = QVBoxLayout(controls_widget)
            controls_layout.setContentsMargins(0, 0, 0, 0)
            controls_layout.setSpacing(4)

            style_button_by_category = {}

            def _style_dialog(category):
                style = category_styles.setdefault(category, self._default_category_style(0)).copy()
                dlg = QDialog(panel)
                dlg.setWindowTitle(f'Category style: {category}')
                layout = QVBoxLayout(dlg)

                form = QFormLayout()
                marker_cb = QComboBox(dlg)
                for label, marker in STYLE_MARKER_OPTIONS:
                    marker_cb.addItem(label, marker)
                marker_index = marker_cb.findData(style.get('marker', 'o'))
                if marker_index >= 0:
                    marker_cb.setCurrentIndex(marker_index)

                marker_size = QDoubleSpinBox(dlg)
                marker_size.setRange(1.0, 25.0)
                marker_size.setDecimals(1)
                marker_size.setSingleStep(0.5)
                marker_size.setValue(float(style.get('markersize', 8)))
                if bubble_active:
                    marker_size.setEnabled(False)
                    marker_size.setToolTip(
                        "Size is controlled by this plot's bubble scaling and can't be overridden here.")

                line_width = QDoubleSpinBox(dlg)
                line_width.setRange(0.1, 10.0)
                line_width.setDecimals(1)
                line_width.setSingleStep(0.2)
                line_width.setValue(float(style.get('linewidth', 1.5)))

                alpha = QDoubleSpinBox(dlg)
                alpha.setRange(0.05, 1.0)
                alpha.setDecimals(2)
                alpha.setSingleStep(0.05)
                alpha.setValue(float(style.get('alpha', 1.0)))

                colour_value = [mcolors.to_hex(style.get('color', '#000000'))]
                colour_btn = QPushButton('Symbol colour', dlg)
                colour_btn.setStyleSheet(f'background-color: {colour_value[0]};')

                def _choose_colour():
                    colour = QColorDialog.getColor(QColor(colour_value[0]), dlg, 'Symbol colour')
                    if colour.isValid():
                        colour_value[0] = colour.name()
                        colour_btn.setStyleSheet(f'background-color: {colour_value[0]};')
                colour_btn.clicked.connect(_choose_colour)

                form.addRow('Symbol shape:', marker_cb)
                form.addRow('Symbol size:', marker_size)
                form.addRow('Symbol colour:', colour_btn)
                form.addRow('Line width:', line_width)
                form.addRow('Transparency:', alpha)
                layout.addLayout(form)

                buttons = QDialogButtonBox(QDialogButtonBox_Ok | QDialogButtonBox_Cancel, dlg)
                layout.addWidget(buttons)
                buttons.accepted.connect(dlg.accept)
                buttons.rejected.connect(dlg.reject)

                if dlg.exec() == QDialog_Accepted:
                    style.update({
                        'marker': marker_cb.currentData(),
                        'markersize': float(marker_size.value()),
                        'color': colour_value[0],
                        'linewidth': float(line_width.value()),
                        'alpha': float(alpha.value()),
                    })
                    category_styles[category] = style
                    _apply_category_style(category)
                    _sync_legend_symbols()

            for category in categories:
                row_widget = QWidget(controls_widget)
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(4)

                checkbox = QCheckBox(f'{category} (n={category_counts.get(category, 0)})', row_widget)
                checkbox.setChecked(True)
                checkbox_by_category[category] = checkbox
                style_btn = QPushButton('Style…', row_widget)
                style_btn.setToolTip(f'Edit plotting style for {category}')
                style_button_by_category[category] = style_btn

                def _make_state_callback(cat, cb):
                    def _on_state_changed(state):
                        visible_state[cat] = cb.isChecked()
                        _refresh_category_visibility()
                    return _on_state_changed

                def _make_style_callback(cat):
                    return lambda: _style_dialog(cat)

                checkbox.stateChanged.connect(_make_state_callback(category, checkbox))
                style_btn.clicked.connect(_make_style_callback(category))
                row_layout.addWidget(checkbox, 1)
                row_layout.addWidget(style_btn, 0)
                controls_layout.addWidget(row_widget)

            controls_layout.addStretch(1)

            scroll = QScrollArea(dock)
            scroll.setWidgetResizable(True)
            scroll.setWidget(controls_widget)
            scroll.setMinimumHeight(120)
            class_layout.addWidget(scroll, 1)
            panel_layout.addWidget(class_group, 1)

            legend_group = QGroupBox('Legend', panel)
            legend_symbol_by_category = {}
            legend_layout = QVBoxLayout(legend_group)
            legend_layout.setSpacing(4)

            for category in categories:
                style = category_styles.get(category, self._default_category_style(0))
                row_widget = QWidget(legend_group)
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(6)

                marker = style.get('marker', 'o')
                colour = style.get('color', '#000000')
                marker_label = _MarkerSymbolWidget(marker, colour, row_widget)
                marker_label.setToolTip(f'{marker} / {colour}')

                category_label = QLabel(f'{category} (n={category_counts.get(category, 0)})', row_widget)
                category_label.setWordWrap(True)

                row_layout.addWidget(marker_label)
                row_layout.addWidget(category_label, 1)
                legend_layout.addWidget(row_widget)
                legend_symbol_by_category[category] = marker_label

            legend_scroll = QScrollArea(dock)
            legend_scroll.setWidgetResizable(True)
            legend_scroll.setWidget(legend_group)
            legend_scroll.setMaximumHeight(180)
            panel_layout.addWidget(legend_scroll, 0)

            dock.setWidget(panel)
            dock.setMinimumWidth(260)
            dock.setFeatures(QDockWidget_Movable | QDockWidget_Floatable)
            window.addDockWidget(RightDockWidgetArea, dock)

            def _set_checkbox_state(category, state):
                checkbox = checkbox_by_category[category]
                if checkbox.isChecked() != state:
                    checkbox.blockSignals(True)
                    checkbox.setChecked(state)
                    checkbox.blockSignals(False)

            def _show_all():
                for category in categories:
                    visible_state[category] = True
                    _set_checkbox_state(category, True)
                _refresh_category_visibility()

            def _hide_all():
                for category in categories:
                    visible_state[category] = False
                    _set_checkbox_state(category, False)
                _refresh_category_visibility()

            def _invert():
                for category in categories:
                    visible_state[category] = not visible_state[category]
                    _set_checkbox_state(category, visible_state[category])
                _refresh_category_visibility()

            def _template_key():
                key = style_template_key or 'default'
                return str(key) if str(key).strip() else 'default'

            def _template_name(default_name=None):
                default_name = default_name or _template_key()
                name, ok = QInputDialog.getText(
                    panel, 'Category style template', 'Template name:', text=str(default_name))
                if not ok:
                    return None
                name = str(name).strip()
                return name or None

            def _save_template():
                name = _template_name(_template_key())
                if not name:
                    return
                data = self._load_style_templates()
                templates = data.setdefault('templates', {})
                templates[name] = {
                    'categoryField': _template_key(),
                    'styles': {
                        str(category): self._normalise_category_style(
                            category_styles.get(category, self._default_category_style(i)), i)
                        for i, category in enumerate(categories)
                    }
                }
                try:
                    path = self._save_style_templates(data)
                except Exception as exc:
                    QMessageBox.critical(panel, 'Save styles', f'Could not save style template:\n{exc}')
                    return
                QMessageBox.information(panel, 'Save styles', f'Style template "{name}" saved to:\n{path}')

            def _load_template():
                data = self._load_style_templates()
                templates = data.get('templates', {}) if isinstance(data, dict) else {}
                if not templates:
                    QMessageBox.information(panel, 'Load styles', 'No saved category style templates were found.')
                    return
                names = sorted(templates.keys(), key=lambda x: str(x).lower())
                preferred = _template_key()
                current_index = names.index(preferred) if preferred in names else 0
                name, ok = QInputDialog.getItem(
                    panel, 'Load styles', 'Select a style template:', names, current_index, False)
                if not ok or not name:
                    return
                template = templates.get(str(name), {})
                styles = template.get('styles', {}) if isinstance(template, dict) else {}
                if not isinstance(styles, dict) or not styles:
                    QMessageBox.warning(panel, 'Load styles',
                                        'The selected style template does not contain any category styles.')
                    return
                for i, category in enumerate(categories):
                    if str(category) in styles:
                        category_styles[category] = self._normalise_category_style(styles[str(category)], i)
                _apply_all_category_styles()

            def _reset_styles():
                reply = QMessageBox.question(
                    panel, 'Reset styles', 'Reset all category styles to the default palette?',
                    QMessageBox_Yes | QMessageBox_No, QMessageBox_No)
                if reply != QMessageBox_Yes:
                    return
                for i, category in enumerate(categories):
                    category_styles[category] = self._default_category_style(i)
                _apply_all_category_styles()

            def _delete_template():
                data = self._load_style_templates()
                templates = data.get('templates', {}) if isinstance(data, dict) else {}
                if not templates:
                    QMessageBox.information(panel, 'Delete styles', 'No saved category style templates were found.')
                    return
                names = sorted(templates.keys(), key=lambda x: str(x).lower())
                preferred = _template_key()
                current_index = names.index(preferred) if preferred in names else 0
                name, ok = QInputDialog.getItem(
                    panel, 'Delete styles', 'Select a style template to delete:', names, current_index, False)
                if not ok or not name:
                    return
                reply = QMessageBox.question(
                    panel, 'Delete styles', f'Delete style template "{name}" permanently?',
                    QMessageBox_Yes | QMessageBox_No, QMessageBox_No)
                if reply != QMessageBox_Yes:
                    return
                templates.pop(str(name), None)
                data['templates'] = templates
                try:
                    path = self._save_style_templates(data)
                except Exception as exc:
                    QMessageBox.critical(panel, 'Delete styles', f'Could not delete style template:\n{exc}')
                    return
                QMessageBox.information(panel, 'Delete styles', f'Style template "{name}" deleted from:\n{path}')

            show_btn.clicked.connect(_show_all)
            hide_btn.clicked.connect(_hide_all)
            invert_btn.clicked.connect(_invert)
            save_template_btn.clicked.connect(_save_template)
            load_template_btn.clicked.connect(_load_template)
            reset_styles_btn.clicked.connect(_reset_styles)
            delete_template_btn.clicked.connect(_delete_template)

            self._category_controls = {
                'dock': dock, 'panel': panel, 'checkboxes': checkbox_by_category,
                'style_buttons': style_button_by_category, 'styles': category_styles,
                'visible_state': visible_state,
            }
            return

        # Fallback for non-Qt Matplotlib backends: on-axes CheckButtons/Button,
        # visibility toggling only (no per-category style editing).
        labels = [f'{category} (n={category_counts.get(category, 0)})' for category in categories]
        label_to_category = dict(zip(labels, categories))
        try:
            fig.subplots_adjust(right=0.68)
        except Exception:
            pass

        check_ax = fig.add_axes([0.72, 0.42, 0.25, 0.45])
        check_ax.set_title('Categories', fontsize=9)
        checks = CheckButtons(check_ax, labels, [True] * len(labels))

        def _set_button_state(index, state):
            if checks.get_status()[index] != state:
                checks.set_active(index)

        def _on_clicked(label):
            category = label_to_category.get(label)
            if category is None:
                return
            index = categories.index(category)
            visible_state[category] = checks.get_status()[index]
            _refresh_category_visibility()

        checks.on_clicked(_on_clicked)
        show_ax = fig.add_axes([0.72, 0.32, 0.075, 0.05])
        hide_ax = fig.add_axes([0.81, 0.32, 0.075, 0.05])
        invert_ax = fig.add_axes([0.90, 0.32, 0.075, 0.05])
        show_btn = Button(show_ax, 'All')
        hide_btn = Button(hide_ax, 'None')
        invert_btn = Button(invert_ax, 'Invert')

        def _show_all(event=None):
            for i, category in enumerate(categories):
                visible_state[category] = True
                _set_button_state(i, True)
            _refresh_category_visibility()

        def _hide_all(event=None):
            for i, category in enumerate(categories):
                visible_state[category] = False
                _set_button_state(i, False)
            _refresh_category_visibility()

        def _invert(event=None):
            for i, category in enumerate(categories):
                visible_state[category] = not visible_state[category]
                _set_button_state(i, visible_state[category])
            _refresh_category_visibility()

        show_btn.on_clicked(_show_all)
        hide_btn.on_clicked(_hide_all)
        invert_btn.on_clicked(_invert)
        self._category_controls = {
            'checkbuttons': checks, 'buttons': (show_btn, hide_btn, invert_btn),
            'visible_state': visible_state, 'axes': (check_ax, show_ax, hide_ax, invert_ax),
        }

    def save_plot(self):
        """Save the current plot."""
        if self.current_fig is None:
            QMessageBox.warning(self, "Warning", "Please generate a plot first.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Plot", "",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)")
        if file_path:
            self.current_fig.savefig(file_path, dpi=300, bbox_inches='tight')
            QMessageBox.information(self, "Success", f"Plot saved to:\n{file_path}")

    def get_numeric_field_names(self):
        """Get numeric field names from the current layer."""
        from qgis.core import QgsField
        try:
            from qgis.PyQt.QtCore import QVariant
        except ImportError:
            import sip
            from PyQt5.QtCore import QVariant

        layer_id = self.layer_combo.currentData()
        if layer_id is None:
            return []
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            return []

        numeric_types = {QVariant.Int, QVariant.LongLong, QVariant.Double,
                        QVariant.UInt, QVariant.ULongLong}
        return [f.name() for f in layer.fields() if f.type() in numeric_types]
    

    def refresh_custom_xy_combos(self):
        """Refresh custom XY combo boxes based on the show-all-fields checkbox."""
        if self.custom_show_all_fields.isChecked():
            field_names = self.get_numeric_field_names()
            none_option = ['1 (none)']
            num_items = field_names          # numerator: no '1 (none)'
            denom_items = none_option + field_names  # denominator: '1 (none)' at top

            for combo in [self.x_num_combo, self.y_num_combo]:
                prev = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(num_items)
                idx = combo.findText(prev)
                combo.setCurrentIndex(idx if idx >= 0 else 0)
                combo.blockSignals(False)

            for combo in [self.x_denom_combo, self.y_denom_combo, self.custom_bubble_field_combo]:
                prev = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(denom_items)
                idx = combo.findText(prev)
                combo.setCurrentIndex(idx if idx >= 0 else 0)
                combo.blockSignals(False)
        else:
            # Restore predefined lists
            for combo in [self.x_num_combo, self.y_num_combo]:
                prev = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(CUSTOM_XY_ELEMENTS[1:])
                idx = combo.findText(prev)
                combo.setCurrentIndex(idx if idx >= 0 else 0)
                combo.blockSignals(False)

            for combo in [self.x_denom_combo, self.y_denom_combo, self.custom_bubble_field_combo]:
                prev = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(CUSTOM_XY_ELEMENTS)
                idx = combo.findText(prev)
                combo.setCurrentIndex(idx if idx >= 0 else 0)
                combo.blockSignals(False)

    def refresh_custom_ternary_combos(self):
        """Refresh ternary apex combo boxes based on the show-all-fields checkbox."""
        num_combos   = [self.tern_a_num_combo,   self.tern_b_num_combo,   self.tern_c_num_combo]
        denom_combos = [self.tern_a_denom_combo, self.tern_b_denom_combo, self.tern_c_denom_combo]
        if self.tern_show_all_fields.isChecked():
            field_names = self.get_numeric_field_names()
            num_items   = field_names
            denom_items = ['1 (none)'] + field_names
        else:
            num_items   = CUSTOM_XY_ELEMENTS[1:]
            denom_items = CUSTOM_XY_ELEMENTS
        for combo in num_combos:
            prev = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(num_items)
            idx = combo.findText(prev)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)
        for combo in denom_combos + [self.tern_bubble_field_combo]:
            prev = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(denom_items)
            idx = combo.findText(prev)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def refresh_petrophysics_combos(self):
        """Populate petrophysics field dropdowns with all fields from the current layer."""
        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        field_names = [f.name() for f in layer.fields()] if layer else []
        for combo in [self.petro_x_field_combo, self.petro_y_field_combo]:
            prev = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(field_names)
            idx = combo.findText(prev)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

        prev = self.petro_bubble_field_combo.currentText()
        self.petro_bubble_field_combo.blockSignals(True)
        self.petro_bubble_field_combo.clear()
        self.petro_bubble_field_combo.addItems(['1 (none)'] + field_names)
        idx = self.petro_bubble_field_combo.findText(prev)
        self.petro_bubble_field_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.petro_bubble_field_combo.blockSignals(False)

    def generate_custom_ternary_plot(self, layer, features, sample_names):
        """Generate a custom ternary (triangle) diagram."""
        def apex_label(num, denom):
            if denom == '1 (none)':
                return num
            return f"{num} / {denom}"

        a_num   = self.tern_a_num_combo.currentText()
        a_denom = self.tern_a_denom_combo.currentText()
        b_num   = self.tern_b_num_combo.currentText()
        b_denom = self.tern_b_denom_combo.currentText()
        c_num   = self.tern_c_num_combo.currentText()
        c_denom = self.tern_c_denom_combo.currentText()

        a_label = apex_label(a_num, a_denom)
        b_label = apex_label(b_num, b_denom)
        c_label = apex_label(c_num, c_denom)

        size_field, bubble_active, bubble_min_size, bubble_max_size, bubble_method = \
            self._read_bubble_controls('tern')

        # Check that all required fields exist in the layer
        elements_needed = set()
        for elem in [a_num, a_denom, b_num, b_denom, c_num, c_denom] + ([size_field] if bubble_active else []):
            if elem != '1 (none)':
                elements_needed.add(elem)
        missing = [e for e in sorted(elements_needed) if find_element_field(layer, e) is None]
        if missing:
            QMessageBox.warning(self, "Warning",
                f"Missing elements: {', '.join(missing)}\nPlot cannot be generated.")
            return

        # Compute raw A, B, C values per sample
        raw_data = []
        valid_features = []
        valid_names = []
        fid_list = []
        size_data = []

        for feature, name in zip(features, sample_names):
            def val(num, denom):
                n = get_custom_element_value(feature, layer, num)
                if num == denom:
                    return 1.0 if n is not None and n > 0 else None
                if denom == '1 (none)':
                    return n if (n is not None and n > 0) else None
                d = get_custom_element_value(feature, layer, denom)
                if n is None or d is None or d == 0:
                    return None
                return n / d

            a = val(a_num, a_denom)
            b = val(b_num, b_denom)
            c = val(c_num, c_denom)

            if a is None or b is None or c is None or (a + b + c) == 0:
                continue

            raw_data.append((a, b, c))
            valid_features.append(feature)
            valid_names.append(name)
            fid_list.append(feature.id())
            size_data.append(get_custom_element_value(feature, layer, size_field) if bubble_active else None)

        if not raw_data:
            QMessageBox.warning(self, "Warning", "No valid data points to plot.")
            return

        bubble_vmin = bubble_vmax = None
        if bubble_active:
            bubble_vmin, bubble_vmax, bubble_active = self._compute_bubble_range(
                'tern', size_data, [True] * len(size_data), bubble_method)
        sample_sizes = None
        if bubble_active:
            sample_sizes = [
                bubble_symbol_size(v, bubble_vmin, bubble_vmax, bubble_min_size, bubble_max_size, bubble_method)
                if v is not None else bubble_min_size
                for v in size_data
            ]

        category_styles, unique_categories = self._build_default_category_styles(valid_names)
        category_colors, category_markers, sample_colors, sample_markers = \
            self._category_arrays_from_styles(category_styles, valid_names)

        fig, ax = plt.subplots(figsize=(10, 9))
        # labels: bottom-left = A, bottom-right = B, top = C
        plot_ternary_axes(ax, [b_label, c_label, a_label])

        # Build pts_data (cartesian) and fid_to_scatter via _scatter_grouped
        # Pass ternary coords as 3-tuples: _scatter_grouped normalises internally
        fid_to_scatter, category_artists = _scatter_grouped(
            ax, raw_data, fid_list, valid_names, sample_colors,
            sample_markers if self.tern_markers.isChecked() else [],
            show_category_legend=self.tern_legend.isChecked(),
            category_colors=category_colors, sample_sizes=sample_sizes,
        )
        artist_registry = {cat: [{'artist': a, 'role': 'scatter'} for a in arts]
                           for cat, arts in category_artists.items()}

        # Build pts_data list in the same fid order for _attach_scatter_selection
        pts_data = []
        ordered_fids = []
        for (a, b, c), fid in zip(raw_data, fid_list):
            if fid in fid_to_scatter:
                x, y = ternary_to_cartesian(a, b, c)
                pts_data.append((x, y))
                ordered_fids.append(fid)

        title = f"{a_label}  –  {b_label}  –  {c_label}  (n={len(raw_data)})"
        ax.set_title(title, fontsize=11, pad=12)

        export_legend_artists = {}
        category_legend_obj = None
        if self.tern_legend.isChecked() and len(unique_categories) > 0:
            export_legend_artists = self._build_category_legend(
                ax, unique_categories, category_styles, Counter(valid_names),
                bbox_to_anchor=(0.5, -0.05), fontsize=8)
            category_legend_obj = ax.get_legend()

        if bubble_active:
            self._add_bubble_size_legend(
                ax, bubble_vmin, bubble_vmax, bubble_min_size, bubble_max_size, bubble_method,
                self._field_display_label(size_field), category_legend_obj)

        plt.tight_layout()
        plt.show()
        self._attach_scatter_selection(fig, ax, pts_data, ordered_fids, fid_to_scatter, layer.id())
        self._open_category_panel(
            fig, artist_registry, category_counts=Counter(valid_names), category_styles=category_styles,
            style_template_key=self._category_field_label(), export_legend_artists=export_legend_artists,
            title='Ternary Plot Categories', bubble_active=bubble_active)
        self.current_fig = fig