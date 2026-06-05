"""
Geochemistry Plotting Tools - Dock Widget
==========================================
Contains the main dockable widget with all plotting functionality.
"""

import os
import json
import matplotlib.colors as mcolors
from qgis.core import QgsProject, QgsVectorLayer, QgsField, NULL
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QListWidget, QListWidgetItem, QCheckBox,
    QFileDialog, QMessageBox, QGroupBox, QTabWidget,
    QGridLayout, QRadioButton, QButtonGroup, QScrollArea
)
from qgis.PyQt.QtCore import Qt, QVariant, pyqtSignal, QSettings

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
    from matplotlib.widgets import RectangleSelector
    from matplotlib.path import Path
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


# =============================================================================
# CATEGORICAL COLOUR MAPPING UTILITIES
# =============================================================================

CATEGORY_MARKERS = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*', 'P', 'X', 'd', '8', 'H']

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
    '1 (none)', 'Co', 'Cr', 'Gd', 'K2O', 'La', 'Lu', 'Mg#', 'MgO', 'Na2O', 'Nb',
    'SiO2', 'Sm', 'Sr', 'Th', 'Ti', 'TiO2', 'V', 'Y', 'Yb', 'Zr'
]

MW_MGO = 40.304
MW_FEO = 71.844


# =============================================================================
# FIELD NAME MATCHING UTILITIES
# =============================================================================
import re

def find_element_field(layer, element):
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

    # 3. Fallback: uppercase prefix match with known suffixes
    for field_name in field_names:
        field_upper = field_name.upper()
        if field_upper.startswith(element_upper):
            remainder = field_upper[len(element_upper):]
            if remainder in ['', '_PPM', '_PPB', '_PCT', '_WT', '_WTPCT',
                           '_WT_PCT', '(PPM)', ' (PPM)', '_[PPM]', '_WT%', 'PPM', 'PPB',
                           'O2_PCT', 'O_PCT', '2O3_PCT', '2O_PCT', '2O5_PCT']:
                return field_name

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


def get_element_value(feature, layer, element, convert_to_ppm=True):
    """Get the value of an element from a feature."""
    field_name = find_element_field(layer, element)
    if field_name:
        try:
            value = float(feature[field_name])
            
            if convert_to_ppm:
                field_upper = field_name.upper()
                # TiO2, MnO, P2O5 are always stored as wt% — convert even when the
                # field has no _pct/_wt suffix (e.g. a plain 'TiO2' column).
                if 'TIO2' in field_upper:
                    value = value * 5995
                elif 'MNO' in field_upper:
                    value = value * 7745
                elif 'P2O5' in field_upper:
                    value = value * 4364
                    
            return value
        except (ValueError, TypeError):
            return None
    return None


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
    
    field_name = find_element_field(layer, element_name)
    if field_name is None:
        return None
    
    try:
        value = float(feature[field_name])
        if value is None or value == NULL:
            return None
        
        if normalize and norm_values and element_name in norm_values:
            norm_val = norm_values.get(element_name)
            if norm_val and norm_val > 0:
                value = value / norm_val
        
        return value
    except (ValueError, TypeError):
        return None


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
                     show_category_legend, category_colors):
    """One ax.scatter() call per category group instead of one per point.

    Handles both binary (x, y) and ternary (a, b, c) coordinate tuples.
    Returns {fid: (PathCollection, local_index)} for use by apply_selection().
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
        cat_key = (name, marker) if sample_markers else name
        if cat_key not in cat_groups:
            cat_groups[cat_key] = {'xs': [], 'ys': [], 'fids': [], 'colors': [],
                                   'marker': marker, 'name': name}
        g = cat_groups[cat_key]
        g['xs'].append(x);  g['ys'].append(y)
        g['fids'].append(fid);  g['colors'].append(color)

    plotted_names = set()
    fid_to_scatter = {}
    for g in cat_groups.values():
        label = None
        if show_category_legend and category_colors and g['name'] not in plotted_names:
            label = g['name']
            plotted_names.add(g['name'])
        sc = ax.scatter(g['xs'], g['ys'], marker=g['marker'], s=80, c=g['colors'],
                        edgecolors='black', linewidths=0.5, zorder=10, label=label)
        for local_idx, fid in enumerate(g['fids']):
            fid_to_scatter[fid] = (sc, local_idx)
    return fid_to_scatter

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
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors)
        
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
        return fid_to_scatter


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
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors)
        
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
        return fid_to_scatter


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
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None):
        plot_ternary_axes(ax, labels=['Zr/4', 'Y', 'Nb×2'])
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors)
        
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
        return fid_to_scatter


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
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors)
        
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
        return fid_to_scatter


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
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors)
        
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
        return fid_to_scatter


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
        ti = get_element_value(feature, layer, 'TiO2')
        if zr is not None and ti is not None and zr > 0 and ti > 0:
            return zr, ti
        return None, None

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None):
        cls.draw_fields(ax)

        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors)

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
        return fid_to_scatter


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
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None):
        cls.draw_fields(ax)

        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors)

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
        return fid_to_scatter


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
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None, fids=None):
        cls.draw_fields(ax)
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors)
        
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
        return fid_to_scatter


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
             category_markers=None, n_samples=None, fids=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)

        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        fid_to_scatter = _scatter_grouped(ax, data, fids or [], sample_names,
                                          sample_colors, sample_markers,
                                          show_category_legend, category_colors)

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
        return fid_to_scatter


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
        self.style_map = {}
        self.style_file_path = None
        self.last_category_colors = {}
        self.last_category_markers = {}
        self.setAllowedAreas(LeftDockWidgetArea | RightDockWidgetArea)
        self.setup_ui()
        self.load_layers()

        # Reload last-used style file
        saved_path = QSettings('geochem_plots', 'geochem_plots').value('style_file', '')
        if saved_path and os.path.isfile(saved_path):
            self.load_style_from_file(saved_path)

        # Connect to layer registry for updates
        QgsProject.instance().layersAdded.connect(self.load_layers)
        QgsProject.instance().layersRemoved.connect(self.load_layers)

    def closeEvent(self, event):
        """Handle close event."""
        self.closingPlugin.emit()
        event.accept()

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

        layer_row = QHBoxLayout()
        layer_row.addWidget(QLabel("Layer:"))
        self.layer_combo = QComboBox()
        self.layer_combo.currentIndexChanged.connect(self.on_layer_changed)
        layer_row.addWidget(self.layer_combo)
        layer_layout.addLayout(layer_row)

        id_row = QHBoxLayout()
        id_row.addWidget(QLabel("Category:"))
        self.id_field_combo = QComboBox()
        self.id_field_combo.currentIndexChanged.connect(self.on_id_field_changed)
        id_row.addWidget(self.id_field_combo)
        layer_layout.addLayout(id_row)

        label_row = QHBoxLayout()
        label_row.addWidget(QLabel("Add label:"))
        self.label_field_combo = QComboBox()
        label_row.addWidget(self.label_field_combo)
        self.discrim_label = QCheckBox()
        self.discrim_label.setChecked(False)
        self.discrim_label.setToolTip("Label selected points using this field")
        label_row.addWidget(self.discrim_label)
        layer_layout.addLayout(label_row)

        main_layout.addWidget(layer_group)

        # Style mapping row
        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("Style:"))
        self.style_file_label = QLabel("(none)")
        self.style_file_label.setStyleSheet("color: gray; font-style: italic;")
        style_row.addWidget(self.style_file_label, stretch=1)
        load_style_btn = QPushButton("Load")
        load_style_btn.setMaximumWidth(50)
        load_style_btn.setToolTip("Load a colour/marker style JSON file")
        load_style_btn.clicked.connect(lambda: self.load_style_from_file())
        save_style_btn = QPushButton("Save")
        save_style_btn.setMaximumWidth(50)
        save_style_btn.setToolTip("Save current plot colours/markers to style file")
        save_style_btn.clicked.connect(lambda: self.save_style_to_file())
        style_row.addWidget(load_style_btn)
        style_row.addWidget(save_style_btn)
        main_layout.addLayout(style_row)

        # Tabs
        self.tab_widget = QTabWidget()

        # Tab 1: Spider Diagram
        spider_tab = QWidget()
        spider_layout = QVBoxLayout(spider_tab)
        spider_layout.setSpacing(5)

        norm_row = QHBoxLayout()
        norm_row.addWidget(QLabel("Normalize:"))
        self.norm_combo = QComboBox()
        for norm_name, norm_values in NORMALIZATION_OPTIONS:
            self.norm_combo.addItem(norm_name, norm_values)
        norm_row.addWidget(self.norm_combo)
        spider_layout.addLayout(norm_row)

        order_row = QHBoxLayout()
        order_row.addWidget(QLabel("Elements:"))
        self.order_combo = QComboBox()
        self.order_combo.addItems(["REE Only (La-Lu)", "Extended (Ba-Yb)", "Extended Alt (Cs-Lu)"])
        order_row.addWidget(self.order_combo)
        spider_layout.addLayout(order_row)

        spider_opts = QHBoxLayout()
        self.spider_legend = QCheckBox("Legend")
        self.spider_legend.setChecked(True)
        self.spider_markers = QCheckBox("Markers")
        self.spider_markers.setChecked(True)
        spider_opts.addWidget(self.spider_legend)
        spider_opts.addWidget(self.spider_markers)
        spider_layout.addLayout(spider_opts)
        spider_layout.addStretch()

        self.tab_widget.addTab(spider_tab, "Spider")

        # Tab 2: Discrimination Diagrams
        discrim_tab = QWidget()
        discrim_layout = QVBoxLayout(discrim_tab)
        discrim_layout.setSpacing(5)

        self.diagram_combo = QComboBox()
        self.diagram_combo.addItems(list(DISCRIMINATION_DIAGRAMS.keys()))
        discrim_layout.addWidget(self.diagram_combo)

        discrim_opts = QHBoxLayout()
        self.discrim_legend = QCheckBox("Field Legend")
        self.discrim_legend.setChecked(True)
        self.discrim_category_legend = QCheckBox("Category Legend")
        self.discrim_category_legend.setChecked(True)
        discrim_opts.addWidget(self.discrim_legend)
        discrim_opts.addWidget(self.discrim_category_legend)
        discrim_layout.addLayout(discrim_opts)
        discrim_layout.addStretch()

        self.tab_widget.addTab(discrim_tab, "Discrimination/Classification")

        # Tab 3: Custom XY Plot
        custom_xy_tab = QWidget()
        custom_xy_layout = QVBoxLayout(custom_xy_tab)
        custom_xy_layout.setSpacing(5)

        # X-axis
        x_group = QGroupBox("X-Axis")
        x_grid = QGridLayout(x_group)
        x_grid.setSpacing(3)
        x_grid.addWidget(QLabel("Num:"), 0, 0)
        self.x_num_combo = QComboBox()
        self.x_num_combo.addItems(CUSTOM_XY_ELEMENTS[1:])
        x_grid.addWidget(self.x_num_combo, 0, 1)
        x_grid.addWidget(QLabel("Denom:"), 0, 2)
        self.x_denom_combo = QComboBox()
        self.x_denom_combo.addItems(CUSTOM_XY_ELEMENTS)
        x_grid.addWidget(self.x_denom_combo, 0, 3)
        custom_xy_layout.addWidget(x_group)

        # Y-axis
        y_group = QGroupBox("Y-Axis")
        y_grid = QGridLayout(y_group)
        y_grid.setSpacing(3)
        y_grid.addWidget(QLabel("Num:"), 0, 0)
        self.y_num_combo = QComboBox()
        self.y_num_combo.addItems(CUSTOM_XY_ELEMENTS[1:])
        y_grid.addWidget(self.y_num_combo, 0, 1)
        y_grid.addWidget(QLabel("Denom:"), 0, 2)
        self.y_denom_combo = QComboBox()
        self.y_denom_combo.addItems(CUSTOM_XY_ELEMENTS)
        y_grid.addWidget(self.y_denom_combo, 0, 3)
        custom_xy_layout.addWidget(y_group)

        # Show all numeric fields checkbox
        self.custom_show_all_fields = QCheckBox("Show all numeric fields")
        self.custom_show_all_fields.setChecked(False)
        self.custom_show_all_fields.toggled.connect(self.refresh_custom_xy_combos)
        custom_xy_layout.addWidget(self.custom_show_all_fields)

        # REE Normalization
        ree_group = QGroupBox("REE Normalization")
        ree_layout = QHBoxLayout(ree_group)
        ree_layout.setSpacing(5)
        ree_layout.addWidget(QLabel("Normalization:"))
        self.ree_norm_combo = QComboBox()
        self.ree_norm_combo.addItem("None")
        for norm_name, norm_values in NORMALIZATION_OPTIONS:
            self.ree_norm_combo.addItem(norm_name)
        self.ree_norm_combo.setCurrentIndex(0)
        ree_layout.addWidget(self.ree_norm_combo)
        ree_group.setMaximumHeight(70)
        custom_xy_layout.addWidget(ree_group)

        # Axis scales
        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("X:"))
        self.x_scale_combo = QComboBox()
        self.x_scale_combo.addItems(["Linear", "Log"])
        scale_row.addWidget(self.x_scale_combo)
        scale_row.addWidget(QLabel("Y:"))
        self.y_scale_combo = QComboBox()
        self.y_scale_combo.addItems(["Linear", "Log"])
        scale_row.addWidget(self.y_scale_combo)
        custom_xy_layout.addLayout(scale_row)

        custom_opts = QHBoxLayout()
        self.custom_legend = QCheckBox("Legend")
        self.custom_legend.setChecked(True)
        self.custom_markers = QCheckBox("Markers")
        self.custom_markers.setChecked(True)
        custom_opts.addWidget(self.custom_legend)
        custom_opts.addWidget(self.custom_markers)
        custom_xy_layout.addLayout(custom_opts)
        custom_xy_layout.addStretch()

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
            grid.setSpacing(3)
            grid.addWidget(QLabel("Num:"), 0, 0)
            num_combo = QComboBox()
            num_combo.addItems(CUSTOM_XY_ELEMENTS[1:])
            grid.addWidget(num_combo, 0, 1)
            grid.addWidget(QLabel("Denom:"), 0, 2)
            denom_combo = QComboBox()
            denom_combo.addItems(CUSTOM_XY_ELEMENTS)
            grid.addWidget(denom_combo, 0, 3)
            setattr(self, num_attr, num_combo)
            setattr(self, denom_attr, denom_combo)
            custom_tern_layout.addWidget(grp)

        self.tern_show_all_fields = QCheckBox("Show all numeric fields")
        self.tern_show_all_fields.setChecked(False)
        self.tern_show_all_fields.toggled.connect(self.refresh_custom_ternary_combos)
        custom_tern_layout.addWidget(self.tern_show_all_fields)

        tern_opts = QHBoxLayout()
        self.tern_legend = QCheckBox("Legend")
        self.tern_legend.setChecked(True)
        self.tern_markers = QCheckBox("Markers")
        self.tern_markers.setChecked(True)
        tern_opts.addWidget(self.tern_legend)
        tern_opts.addWidget(self.tern_markers)
        custom_tern_layout.addLayout(tern_opts)
        custom_tern_layout.addStretch()

        self.tab_widget.addTab(custom_tern_tab, "Custom Ternary")

        # Tab 5: Minerals (Apatite Group Classification)
        minerals_tab = QWidget()
        minerals_layout = QVBoxLayout(minerals_tab)
        minerals_layout.setSpacing(5)

        minerals_opts = QHBoxLayout()
        self.minerals_legend = QCheckBox("Field Legend")
        self.minerals_legend.setChecked(True)
        self.minerals_category_legend = QCheckBox("Category Legend")
        self.minerals_category_legend.setChecked(True)
        minerals_opts.addWidget(self.minerals_legend)
        minerals_opts.addWidget(self.minerals_category_legend)
        minerals_layout.addLayout(minerals_opts)
        minerals_layout.addStretch()

        self.tab_widget.addTab(minerals_tab, "Minerals")

        # Tab 6: Petrophysics
        petro_tab = QWidget()
        petro_layout = QVBoxLayout(petro_tab)
        petro_layout.setSpacing(5)

        # X Axis (Density)
        petro_x_group = QGroupBox("X-Axis (Density)")
        petro_x_grid = QGridLayout(petro_x_group)
        petro_x_grid.setSpacing(3)
        petro_x_grid.addWidget(QLabel("Field:"), 0, 0)
        self.petro_x_field_combo = QComboBox()
        petro_x_grid.addWidget(self.petro_x_field_combo, 0, 1, 1, 3)
        petro_x_grid.addWidget(QLabel("Units:"), 1, 0)
        self.petro_x_unit_combo = QComboBox()
        self.petro_x_unit_combo.addItems([
            "No Scaling",
            "CGS (no scaling)",
            "SI (÷ 1000)",
        ])
        petro_x_grid.addWidget(self.petro_x_unit_combo, 1, 1, 1, 3)
        petro_layout.addWidget(petro_x_group)

        # Y Axis (Magnetic Susceptibility)
        petro_y_group = QGroupBox("Y-Axis (Magnetic Susceptibility)")
        petro_y_grid = QGridLayout(petro_y_group)
        petro_y_grid.setSpacing(3)
        petro_y_grid.addWidget(QLabel("Field:"), 0, 0)
        self.petro_y_field_combo = QComboBox()
        petro_y_grid.addWidget(self.petro_y_field_combo, 0, 1, 1, 3)
        petro_y_grid.addWidget(QLabel("Units:"), 1, 0)
        self.petro_y_unit_combo = QComboBox()
        self.petro_y_unit_combo.addItems([
            "No Scaling",
            "CGS (× 4π)",
            "SI (no scaling)",
            "SI ×10⁻³",
        ])
        petro_y_grid.addWidget(self.petro_y_unit_combo, 1, 1, 1, 3)
        petro_layout.addWidget(petro_y_group)

        petro_opts = QHBoxLayout()
        self.petro_legend = QCheckBox("Legend")
        self.petro_legend.setChecked(True)
        self.petro_markers = QCheckBox("Markers")
        self.petro_markers.setChecked(True)
        petro_opts.addWidget(self.petro_legend)
        petro_opts.addWidget(self.petro_markers)
        petro_layout.addLayout(petro_opts)
        petro_layout.addStretch()

        self.tab_widget.addTab(petro_tab, "Petrophysics")

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
        scroll_area.setHorizontalScrollBarPolicy(Qt_ScrollBarAlwaysOff)        
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
        field_names = [field.name() for field in layer.fields()]
        for field_name in field_names:
            self.id_field_combo.addItem(field_name)
            self.label_field_combo.addItem(field_name)

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
        features = []
        sample_names = []
        for item in selected_items:
            fid = item.data(Qt_UserRole)
            feature = layer.getFeature(fid)
            features.append(feature)
            if id_field:
                sample_names.append(str(feature[id_field]))
            else:
                sample_names.append(f"Sample {fid}")

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
                field_name = find_element_field(layer, element)
                if not field_name:
                    if element not in missing_from_dataset:
                        missing_from_dataset.append(element)
                    normalized_values.append(value)
                    continue

                try:
                    raw_value = feature[field_name]
                    if raw_value is not None and raw_value != NULL:
                        raw_value = float(raw_value)

                        field_upper = field_name.upper()
                        if element == 'K' and 'K2O' in field_upper and ('PCT' in field_upper or 'WT' in field_upper or field_upper == 'K2O'):
                            raw_value = raw_value * 8301
                        elif element == 'P' and 'P2O5' in field_upper and ('PCT' in field_upper or 'WT' in field_upper or field_upper == 'P2O5'):
                            raw_value = raw_value * 4364
                        elif element == 'Ti' and 'TIO2' in field_upper and ('PCT' in field_upper or 'WT' in field_upper or field_upper == 'TIO2'):
                            raw_value = raw_value * 5995

                        if raw_value > 0 and element in norm_values and norm_values[element] > 0:
                            value = raw_value / norm_values[element]
                except (ValueError, TypeError):
                    pass
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

        category_colors, sample_colors, unique_categories, category_markers, sample_markers = create_categorical_color_map(sample_names)
        category_colors, category_markers, sample_colors, sample_markers = self.apply_style_overrides(category_colors, category_markers, sample_names)

        plotted_categories = set()
        line_to_fid = {}

        for i, (values, name, feature) in enumerate(zip(plot_data, sample_names, features)):
            marker = sample_markers[i] if self.spider_markers.isChecked() else None
            color = sample_colors[i]
            label = name if name not in plotted_categories else None
            plotted_categories.add(name)

            lines = ax.plot(x_positions, values, marker=marker, markersize=8, linewidth=1.5,
                   label=label, color=color, markerfacecolor='white' if marker else None,
                   markeredgecolor=color, markeredgewidth=1.5)
            line_to_fid[lines[0]] = feature.id()

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

        if self.spider_legend.isChecked():
            n_categories = len(unique_categories)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=9,
                     ncol=ncol, framealpha=0.9, borderaxespad=0.)

        plt.tight_layout()
        fig.subplots_adjust(bottom=0.25)
        plt.show()
        self._attach_spider_selection(fig, line_to_fid, layer.id())
        self.current_fig = fig

    def add_classification_field(self):
        """Add or update a classification field on the layer for the current discrimination diagram."""
        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            QMessageBox.warning(self, "Warning", "Please select a valid layer.")
            return

        if self.tab_widget.currentIndex() == 4:
            diagram_class = ApatiteGroupPlot
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

        data = []
        for feature in features:
            coords = diagram_class.calculate_coordinates(feature, layer)
            data.append(coords)

        valid_count = sum(1 for coords in data if coords[0] is not None)

        # Build pts_data and fid_list for selection (handles both binary and ternary)
        pts_data = []
        fid_list = []
        for coords, feature in zip(data, features):
            if coords[0] is None:
                continue
            if len(coords) == 3:
                if coords[2] is None:
                    continue
                x, y = ternary_to_cartesian(*coords)
            else:
                if coords[1] is None:
                    continue
                x, y = coords[0], coords[1]
            pts_data.append((x, y))
            fid_list.append(feature.id())

        category_colors, sample_colors, unique_categories, category_markers, sample_markers = create_categorical_color_map(sample_names)
        category_colors, category_markers, sample_colors, sample_markers = self.apply_style_overrides(category_colors, category_markers, sample_names)

        fig, ax = plt.subplots(figsize=(10, 8))
        fid_to_scatter = diagram_class.plot(ax, data, sample_names,
                          show_legend=self.discrim_legend.isChecked(),
                          show_category_legend=self.discrim_category_legend.isChecked(),
                          sample_colors=sample_colors, category_colors=category_colors,
                          sample_markers=sample_markers, category_markers=category_markers,
                          n_samples=valid_count, fids=fid_list)
        plt.tight_layout()
        fig.subplots_adjust(bottom=0.2)
        plt.show()
        self._attach_scatter_selection(fig, ax, pts_data, fid_list, fid_to_scatter, layer.id())
        self.current_fig = fig

    def generate_minerals_plot(self, layer, features, sample_names):
        """Generate apatite group classification plot (Sr/Y vs Sum LREE)."""
        data = []
        for feature in features:
            coords = ApatiteGroupPlot.calculate_coordinates(feature, layer)
            data.append(coords)

        valid_count = sum(1 for coords in data if coords[0] is not None)
        if valid_count == 0:
            QMessageBox.warning(self, "Warning",
                "No valid data points. Layer needs La, Ce, Pr, Nd, Sr and Y fields.")
            return

        pts_data = []
        fid_list = []
        for coords, feature in zip(data, features):
            if coords[0] is None or coords[1] is None:
                continue
            pts_data.append((coords[0], coords[1]))
            fid_list.append(feature.id())

        category_colors, sample_colors, unique_categories, category_markers, sample_markers = \
            create_categorical_color_map(sample_names)
        category_colors, category_markers, sample_colors, sample_markers = \
            self.apply_style_overrides(category_colors, category_markers, sample_names)

        fig, ax = plt.subplots(figsize=(10, 8))
        fid_to_scatter = ApatiteGroupPlot.plot(
            ax, data, sample_names,
            show_legend=self.minerals_legend.isChecked(),
            show_category_legend=self.minerals_category_legend.isChecked(),
            sample_colors=sample_colors, category_colors=category_colors,
            sample_markers=sample_markers, category_markers=category_markers,
            n_samples=valid_count, fids=fid_list)
        plt.tight_layout()
        fig.subplots_adjust(bottom=0.2)
        plt.show()
        self._attach_scatter_selection(fig, ax, pts_data, fid_list, fid_to_scatter, layer.id())
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

        x_data, y_data = [], []
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
            if xv is not None and yv is not None:
                valid_count += 1

        if valid_count == 0:
            QMessageBox.warning(self, "Warning", "No valid data points to plot.")
            return

        category_colors, sample_colors, unique_categories, category_markers, sample_markers = \
            create_categorical_color_map(sample_names)
        category_colors, category_markers, sample_colors, sample_markers = \
            self.apply_style_overrides(category_colors, category_markers, sample_names)

        fig, ax = plt.subplots(figsize=(12, 9))

        ax.set_yscale('log')

        default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        plotted_categories = set()
        pts_data, fid_list = [], []
        fid_to_scatter = {}

        cat_groups = {}
        for i, (x, y, name, feature) in enumerate(zip(x_data, y_data, sample_names, features)):
            if x is None or y is None:
                continue
            color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
            marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
            cat_key = (name, marker) if self.petro_markers.isChecked() else name
            if cat_key not in cat_groups:
                cat_groups[cat_key] = {'xs': [], 'ys': [], 'fids': [], 'colors': [],
                                       'marker': marker, 'name': name}
            g = cat_groups[cat_key]
            g['xs'].append(x); g['ys'].append(y)
            g['fids'].append(feature.id()); g['colors'].append(color)
            pts_data.append((x, y))
            fid_list.append(feature.id())

        for g in cat_groups.values():
            label = None
            if self.petro_legend.isChecked() and g['name'] not in plotted_categories:
                label = g['name']
                plotted_categories.add(g['name'])
            scatter_kw = dict(s=80, c=g['colors'], edgecolors='black',
                              linewidths=0.5, zorder=10, label=label)
            if self.petro_markers.isChecked():
                scatter_kw['marker'] = g['marker']
            sc = ax.scatter(g['xs'], g['ys'], **scatter_kw)
            for local_idx, fid in enumerate(g['fids']):
                fid_to_scatter[fid] = (sc, local_idx)

        ax.set_xlabel(f"{x_field}{x_unit_label}", fontsize=12)
        ax.set_ylabel(f"{y_field}{y_unit_label}", fontsize=12)
        ax.set_title(f"{y_field} vs {x_field} (n={valid_count})", fontsize=14)
        ax.grid(True, alpha=0.3)

        if self.petro_legend.isChecked() and unique_categories:
            n_categories = len(unique_categories)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=8,
                      ncol=ncol, framealpha=0.9, borderaxespad=0.)

        plt.tight_layout()
        fig.subplots_adjust(bottom=0.2)
        plt.show()
        self._attach_scatter_selection(fig, ax, pts_data, fid_list, fid_to_scatter, layer.id())
        self.current_fig = fig

    def generate_custom_xy_plot(self, layer, features, sample_names):
        """Generate custom XY plot."""
        x_num = self.x_num_combo.currentText()
        x_denom = self.x_denom_combo.currentText()
        y_num = self.y_num_combo.currentText()
        y_denom = self.y_denom_combo.currentText()
        
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
                if elem == '1 (none)':
                    return ''
                elif elem == 'Mg#':
                    return ''
                elif any(elem.endswith(ox) for ox in ['O', 'O2', '2O', '2O3', '2O5']):
                    return ' (wt%)'
                else:
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
        for elem in [x_num, x_denom, y_num, y_denom]:
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
        valid_count = 0
        
        for feature in features:
            x_num_val = get_custom_element_value(feature, layer, x_num, 
                                                  normalize=(norm_values is not None and x_num in REE_ELEMENTS),
                                                  norm_values=norm_values)
            x_denom_val = get_custom_element_value(feature, layer, x_denom,
                                                    normalize=(norm_values is not None and x_denom in REE_ELEMENTS),
                                                    norm_values=norm_values)
            
            y_num_val = get_custom_element_value(feature, layer, y_num,
                                                  normalize=(norm_values is not None and y_num in REE_ELEMENTS),
                                                  norm_values=norm_values)
            y_denom_val = get_custom_element_value(feature, layer, y_denom,
                                                    normalize=(norm_values is not None and y_denom in REE_ELEMENTS),
                                                    norm_values=norm_values)
            
            x_val = None
            y_val = None
            
            if (x_num_val is not None and x_denom_val is not None and 
                x_num_val > 0 and x_denom_val > 0):
                x_val = x_num_val / x_denom_val
            
            if (y_num_val is not None and y_denom_val is not None and 
                y_num_val > 0 and y_denom_val > 0):
                y_val = y_num_val / y_denom_val
            
            x_data.append(x_val)
            y_data.append(y_val)
            
            if x_val is not None and y_val is not None:
                valid_count += 1
        
        if valid_count == 0:
            QMessageBox.warning(self, "Warning", "No valid data points to plot.")
            return
        
        category_colors, sample_colors, unique_categories, category_markers, sample_markers = create_categorical_color_map(sample_names)
        category_colors, category_markers, sample_colors, sample_markers = self.apply_style_overrides(category_colors, category_markers, sample_names)

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

        # Group points by category so we make one ax.scatter() call per group instead
        # of one per point, eliminating the O(n_points) PathCollection overhead.
        cat_groups = {}
        for i, (x, y, name, feature) in enumerate(zip(x_data, y_data, sample_names, features)):
            if x is not None and y is not None:
                color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
                marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
                cat_key = (name, marker) if self.custom_markers.isChecked() else name
                if cat_key not in cat_groups:
                    cat_groups[cat_key] = {'xs': [], 'ys': [], 'fids': [], 'colors': [],
                                           'marker': marker, 'name': name}
                g = cat_groups[cat_key]
                g['xs'].append(x)
                g['ys'].append(y)
                g['fids'].append(feature.id())
                g['colors'].append(color)
                pts_data.append((x, y))
                fid_list.append(feature.id())

        for cat_key, g in cat_groups.items():
            label = None
            if self.custom_legend.isChecked() and g['name'] not in plotted_categories:
                label = g['name']
                plotted_categories.add(g['name'])
            scatter_kw = dict(s=80, c=g['colors'], edgecolors='black',
                              linewidths=0.5, zorder=10, label=label)
            if self.custom_markers.isChecked():
                scatter_kw['marker'] = g['marker']
            sc = ax.scatter(g['xs'], g['ys'], **scatter_kw)
            for local_idx, fid in enumerate(g['fids']):
                fid_to_scatter[fid] = (sc, local_idx)

        ax.set_xlabel(x_label, fontsize=12)
        ax.set_ylabel(y_label, fontsize=12)

        title = f"{y_label} vs {x_label} (n={valid_count})"
        if norm_values:
            title += f"\nREE normalized to {norm_name}"
        ax.set_title(title, fontsize=14)

        ax.grid(True, alpha=0.3)

        if self.custom_legend.isChecked() and len(unique_categories) > 0:
            n_categories = len(unique_categories)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=8,
                     ncol=ncol, framealpha=0.9, borderaxespad=0.)

        plt.tight_layout()
        fig.subplots_adjust(bottom=0.2)
        plt.show()
        self._attach_scatter_selection(fig, ax, pts_data, fid_list, fid_to_scatter, layer.id())
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
                            ann = ax.annotate(
                                str(val), xy=(x, y),
                                xytext=(6, 0), textcoords='offset points',
                                fontsize=8, va='center'
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
    # Style file management
    # ------------------------------------------------------------------

    def apply_style_overrides(self, category_colors, category_markers, sample_names):
        """Override auto-generated colors/markers with any entries in style_map.
        Returns updated (category_colors, category_markers, sample_colors, sample_markers).
        """
        for cat, style in self.style_map.items():
            if cat not in category_colors:
                continue
            if 'color' in style:
                try:
                    category_colors[cat] = mcolors.to_rgba(style['color'])
                except ValueError:
                    pass
            if 'marker' in style:
                category_markers[cat] = style['marker']
        sample_colors = [category_colors[n] for n in sample_names]
        sample_markers = [category_markers[n] for n in sample_names]
        self.last_category_colors = dict(category_colors)
        self.last_category_markers = dict(category_markers)
        return category_colors, category_markers, sample_colors, sample_markers

    def load_style_from_file(self, path=None):
        """Load colour/marker style mappings from a JSON file."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Load Style File", "", "JSON Files (*.json);;All Files (*)")
            if not path:
                return
        try:
            with open(path) as f:
                self.style_map = json.load(f)
            self.style_file_path = path
            QSettings('geochem_plots', 'geochem_plots').setValue('style_file', path)
            self.style_file_label.setText(os.path.basename(path))
            self.style_file_label.setStyleSheet("")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load style file:\n{e}")

    def save_style_to_file(self):
        """Merge current plot colours/markers into style_map and save to JSON."""
        if not self.last_category_colors:
            QMessageBox.information(self, "No plot yet",
                "Generate a plot first so there are colours/markers to save.")
            return
        # Merge latest plot colors into style_map
        for cat, color in self.last_category_colors.items():
            self.style_map[cat] = {
                'color': mcolors.to_hex(color),
                'marker': self.last_category_markers.get(cat, 'o'),
            }
        # Ask for path if none set yet
        if self.style_file_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Style File", "", "JSON Files (*.json);;All Files (*)")
            if not path:
                return
            self.style_file_path = path
            QSettings('geochem_plots', 'geochem_plots').setValue('style_file', path)
            self.style_file_label.setText(os.path.basename(path))
            self.style_file_label.setStyleSheet("")
        with open(self.style_file_path, 'w') as f:
            json.dump(self.style_map, f, indent=2, sort_keys=True)

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

            for combo in [self.x_denom_combo, self.y_denom_combo]:
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

            for combo in [self.x_denom_combo, self.y_denom_combo]:
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
        for combo in denom_combos:
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

        # Check that all required fields exist in the layer
        elements_needed = set()
        for elem in [a_num, a_denom, b_num, b_denom, c_num, c_denom]:
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

        if not raw_data:
            QMessageBox.warning(self, "Warning", "No valid data points to plot.")
            return

        category_colors, sample_colors, unique_categories, category_markers, sample_markers = \
            create_categorical_color_map(valid_names)
        category_colors, category_markers, sample_colors, sample_markers = \
            self.apply_style_overrides(category_colors, category_markers, valid_names)

        fig, ax = plt.subplots(figsize=(10, 9))
        # labels: bottom-left = A, bottom-right = B, top = C
        plot_ternary_axes(ax, [b_label, c_label, a_label])

        # Build pts_data (cartesian) and fid_to_scatter via _scatter_grouped
        # Pass ternary coords as 3-tuples: _scatter_grouped normalises internally
        fid_to_scatter = _scatter_grouped(
            ax, raw_data, fid_list, valid_names, sample_colors,
            sample_markers if self.tern_markers.isChecked() else [],
            show_category_legend=self.tern_legend.isChecked(),
            category_colors=category_colors,
        )

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

        if self.tern_legend.isChecked() and len(unique_categories) > 0:
            n_cat = len(unique_categories)
            ncol = max(1, min(6, (n_cat + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05),
                      fontsize=8, ncol=ncol, framealpha=0.9, borderaxespad=0.)

        plt.tight_layout()
        plt.show()
        self._attach_scatter_selection(fig, ax, pts_data, ordered_fids, fid_to_scatter, layer.id())
        self.current_fig = fig