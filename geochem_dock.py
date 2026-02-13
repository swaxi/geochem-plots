"""
Geochemistry Plotting Tools - Dock Widget
==========================================
Contains the main dockable widget with all plotting functionality.
"""

import os
from qgis.core import QgsProject, QgsVectorLayer, NULL
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QListWidget, QListWidgetItem, QCheckBox,
    QFileDialog, QMessageBox, QGroupBox, QTabWidget,
    QGridLayout, QRadioButton, QButtonGroup, QScrollArea
)
from qgis.PyQt.QtCore import Qt, pyqtSignal

try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    from matplotlib.patches import Polygon
    from matplotlib.lines import Line2D
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


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

CHONDRITE_VALUES = {
    'Ba': 2.41, 'Rb': 2.32, 'Cs': 0.188, 'Sr': 7.26, 'K': 545, 'K2O': 0.0545,
    'Th': 0.029, 'U': 0.0074, 'Nb': 0.246, 'Ta': 0.014, 'Zr': 3.87, 'Hf': 0.1066,
    'Ti': 445, 'TiO2': 0.0728, 'P': 1220, 'P2O5': 0.28,
    'La': 0.237, 'Ce': 0.612, 'Pr': 0.095, 'Nd': 0.467, 'Sm': 0.153, 'Eu': 0.058,
    'Gd': 0.2055, 'Tb': 0.0374, 'Dy': 0.254, 'Ho': 0.0566, 'Er': 0.1655,
    'Tm': 0.0255, 'Yb': 0.170, 'Lu': 0.0254, 'Y': 1.57, 'Sc': 5.92, 'Pb': 2.47,
}

PRIMITIVE_MANTLE_VALUES = {
    'Ba': 6.6, 'Rb': 0.6, 'Cs': 0.021, 'Sr': 19.9, 'K': 250,
    'Th': 0.0795, 'U': 0.0203, 'Nb': 0.658, 'Ta': 0.037,
    'La': 0.648, 'Ce': 1.675, 'Pr': 0.254, 'Nd': 1.25, 'Sm': 0.406,
    'Eu': 0.154, 'Gd': 0.544, 'Tb': 0.099, 'Dy': 0.674, 'Ho': 0.149,
    'Er': 0.438, 'Tm': 0.068, 'Yb': 0.441, 'Lu': 0.0675, 'Y': 4.3,
    'Zr': 10.5, 'Hf': 0.283, 'Ti': 1300, 'P': 95, 'Pb': 0.15, 'Sc': 16.2,
}

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
                
                if 'TIO2' in field_upper and ('PCT' in field_upper or 'WT' in field_upper):
                    value = value * 5995
                elif 'MNO' in field_upper and ('PCT' in field_upper or 'WT' in field_upper):
                    value = value * 7745
                elif 'P2O5' in field_upper and ('PCT' in field_upper or 'WT' in field_upper):
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

class Pearce1996_NbY_ZrTi:
    """Nb/Y vs Zr/Ti diagram (Winchester & Floyd 1977; Pearce 1996)."""
    
    name = "Zr/Ti vs Nb/Y"
    reference = "Winchester & Floyd (1977); Pearce (1996)"

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
        ax.plot([0.01, 10.0], [0.03, 0.3], 'k-', linewidth=1.0)
        ax.plot([0.01, 10.0], [0.008, 0.08], 'k-', linewidth=1.0)
        ax.plot([0.1, 0.7], [1.1, 0.3], 'k-', linewidth=1)
        ax.plot([0.7, 7.5], [0.3, 1.1], 'k-', linewidth=1)
        ax.plot([0.7, 0.7], [0.3, 0.001], 'k-', linewidth=1)
        ax.plot([3.5, 3.5], [0.72, 0.001], 'k-', linewidth=1)

        ax.text(0.1, 0.006, 'Basalt', fontsize=11, ha='center', va='center')
        ax.text(0.1, 0.05, 'Andesite', fontsize=8, ha='center', va='center', style='italic',rotation=14)
        ax.text(0.1, 0.025, 'Basaltic andesite', fontsize=8, ha='center', va='center', style='italic',rotation=14)
        ax.text(0.1, 0.15, 'Rhyolite\nDacite', fontsize=10, ha='center', va='center')
        ax.text(1.8, 0.2, 'Trachyte', fontsize=10, ha='center', va='center')
        ax.text(1.8, 0.065, 'Trachy-\nandesite', fontsize=9, ha='center', va='center')
        ax.text(1.8, 0.015, 'Alkali\nBasalt', fontsize=9, ha='center', va='center')
        ax.text(0.7, 0.6, 'Alkali\nRhyolite', fontsize=9, ha='center', va='center')
        ax.text(5.0, 0.4, 'Phonolite', fontsize=10, ha='center', va='center')
        ax.text(5.0, 0.09, 'Tephri-\nphonolite', fontsize=9, ha='center', va='center')
        ax.text(5.0, 0.02, 'Foidite', fontsize=10, ha='center', va='center')
        ax.text(0.12, 0.0015, 'subalkaline', fontsize=9, ha='center', va='top')
        ax.text(1.8, 0.0015, 'alkaline', fontsize=9, ha='center', va='top')
        ax.text(6, 0.0015, 'ultra-\nalkaline', fontsize=8, ha='center', va='top')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        plotted_categories = set()
        
        for i, ((x, y), name) in enumerate(zip(data, sample_names)):
            if x is not None and y is not None:
                color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
                marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
                label = name if (show_category_legend and category_colors and name not in plotted_categories) else None
                plotted_categories.add(name)
                
                ax.scatter(x, y, marker=marker, s=80, c=[color], edgecolors='black',
                          linewidths=0.5, zorder=10, label=label)
        
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


class Meschede1986_Ternary:
    """Zr/4-Nb*2-Y ternary diagram (Meschede, 1986)."""
    
    name = "Zr/4 - Nb×2 - Y"
    reference = "Meschede (1986)"

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        zr = get_element_value(feature, layer, 'Zr')
        nb = get_element_value(feature, layer, 'Nb')
        y = get_element_value(feature, layer, 'Y')
        
        if all(v is not None and v >= 0 for v in [zr, nb, y]):
            return zr/4, y, nb*2
        return None, None, None

    @classmethod
    def draw_fields(cls, ax):
        outer = [
            (50, 50, 0), (60, 29, 11), (50, 13, 37), (13, 8, 79), (23, 77, 0),
        ]
        
        for i in range(len(outer) - 1):
            draw_ternary_line(ax, outer[i], outer[i+1], color='k', linewidth=1.5, linestyle='-')
        
        draw_ternary_line(ax, (60, 29, 11), (34, 17, 49), color='k', linewidth=1, linestyle='--')
        draw_ternary_line(ax, (34, 17, 49), (17, 27, 56), color='k', linewidth=1, linestyle='--')
        draw_ternary_line(ax, (60, 29, 11), (38, 28, 34), color='k', linewidth=1, linestyle='--')
        draw_ternary_line(ax, (38, 28, 34), (18, 33, 49), color='k', linewidth=1, linestyle='--')
        draw_ternary_line(ax, (37, 29, 34), (37, 40, 23), color='k', linewidth=1, linestyle='--')
        draw_ternary_line(ax, (21, 57, 22), (37, 40, 23), color='k', linewidth=1, linestyle='--')
        draw_ternary_line(ax, (52, 43, 4), (37, 40, 23), color='k', linewidth=1, linestyle='--')
        
        ternary_text(ax, 30, 15, 55, 'AI', fontsize=11, ha='center', va='center', fontweight='bold')
        ternary_text(ax, 35, 25, 40, 'AII', fontsize=11, ha='center', va='center', fontweight='bold')
        ternary_text(ax, 28, 37, 35, 'B', fontsize=11, ha='center', va='center', fontweight='bold')
        ternary_text(ax, 50, 35, 15, 'C', fontsize=11, ha='center', va='center', fontweight='bold')
        ternary_text(ax, 35, 55, 10, 'D', fontsize=11, ha='center', va='center', fontweight='bold')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None):
        plot_ternary_axes(ax, labels=['Zr/4', 'Y', 'Nb×2'])
        cls.draw_fields(ax)
        
        default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        plotted_categories = set()
        
        for i, (coords, name) in enumerate(zip(data, sample_names)):
            if coords[0] is not None and coords[1] is not None and coords[2] is not None:
                x, y = ternary_to_cartesian(*coords)
                color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
                marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
                label = name if (show_category_legend and category_colors and name not in plotted_categories) else None
                plotted_categories.add(name)
                
                ax.scatter(x, y, marker=marker, s=80, c=[color], edgecolors='black',
                          linewidths=0.5, zorder=10, label=label)
        
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


class Pearce1984_YNb:
    """Nb vs Y diagram for granites (Pearce et al., 1984)."""
    
    name = "Nb vs Y"
    reference = "Pearce et al. (1984)"

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
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        plotted_categories = set()
        
        for i, ((x, y), name) in enumerate(zip(data, sample_names)):
            if x is not None and y is not None:
                color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
                marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
                label = name if (show_category_legend and category_colors and name not in plotted_categories) else None
                plotted_categories.add(name)
                
                ax.scatter(x, y, marker=marker, s=80, c=[color], edgecolors='black',
                          linewidths=0.5, zorder=10, label=label)
        
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


class Pearce1984_YNbRb:
    """Rb vs (Y+Nb) diagram for granites (Pearce et al., 1984)."""
    
    name = "Rb vs (Y+Nb)"
    reference = "Pearce et al. (1984)"

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
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        plotted_categories = set()
        
        for i, ((x, y), name) in enumerate(zip(data, sample_names)):
            if x is not None and y is not None:
                color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
                marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
                label = name if (show_category_legend and category_colors and name not in plotted_categories) else None
                plotted_categories.add(name)
                
                ax.scatter(x, y, marker=marker, s=80, c=[color], edgecolors='black',
                          linewidths=0.5, zorder=10, label=label)
        
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


class PearceCann1973_ZrTi:
    """Ti vs Zr diagram (Pearce & Cann, 1973)."""
    
    name = "Ti vs Zr"
    reference = "Pearce & Cann (1973)"

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        zr = get_element_value(feature, layer, 'Zr')
        ti = get_element_value(feature, layer, 'TiO2')

        if zr is not None and ti is not None and zr > 0 and ti > 0:
            return zr, ti
        return None, None

    @classmethod
    def draw_fields(cls, ax):
        ax.plot([100, 80, 4, 19, 59, 84], [1600, 1800, 1600, 4400, 8600, 6200], 'b-', linewidth=1.5)
        ax.plot([100, 84, 80, 44, 36, 48, 88], [7400, 6200, 5900, 3000, 3800, 5900, 9000], 'b-', linewidth=1.5)
        ax.plot([80, 80], [1800, 5900], 'b-', linewidth=1.5)
        
        ax.text(22, 2700, 'IAT', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(60, 5500, 'MORB + IAT\n+ CAB', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(87, 7500, 'MORB', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(93, 3500, 'CAB', fontsize=12, ha='center', va='center', fontweight='bold')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None):
        cls.draw_fields(ax)
        
        default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        plotted_categories = set()
        
        for i, ((x, y), name) in enumerate(zip(data, sample_names)):
            if x is not None and y is not None:
                color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
                marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
                label = name if (show_category_legend and category_colors and name not in plotted_categories) else None
                plotted_categories.add(name)
                
                ax.scatter(x, y, marker=marker, s=80, c=[color], edgecolors='black',
                          linewidths=0.5, zorder=10, label=label)
        
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


class Wilson1989_TAS:
    """Na2O + K2O vs SiO2 Cox et al. (1979) adapted by Wilson (1989) for plutonic rocks"""
    
    name = "Na2O + K2O vs SiO2"
    reference = "Wilson (1989) Plutonic Rocks"

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        na = get_element_value(feature, layer, 'Na2O')
        k = get_element_value(feature, layer, 'K2O')
        si = get_element_value(feature, layer, 'SiO2')

        if na is not None and k is not None and si is not None and na > 0 and k > 0 and si > 0:
            return si, (na + k)
        return None, None

    @classmethod
    def draw_fields(cls, ax):
        ax.plot([35.3, 35.3, 40.0, 48.2, 51.2, 51.8, 61.5, 68.8, 73.8, 74.8, 74.8, 73.9, 69.6, 62.5, 54.6, 51.3, 43.7, 40.7, 38.7, 35.3], 
                [6.3, 6.7,9.5, 15.0, 16.8, 16.8, 14.1, 11.8, 9.7, 8.9, 7.9, 7.1, 5.5, 3.5, 1.7, 1.6, 1.9, 3.2, 4.2, 6.3], 'b-', linewidth=1.5)
        ax.plot([43.7, 46.9, 51.4, 53.1, 58.5, 63.3, 66.3, 71.2, 74.7], 
                [1.9, 3.4, 5.2, 5.7, 7.0, 7.7, 8.0, 8.3, 8.4], 'g--', linewidth=1.5)
        ax.plot([38.7, 43.0, 44.9, 50.8], [4.2, 8.4, 9.6, 13.4], 'b-', linewidth=1.5)
        ax.plot([40.7, 44.0, 47.5, 49.3, 54.2], [3.2, 5.9, 8.6, 9.3, 11.3], 'b-', linewidth=1.5)
        ax.plot([48.2, 50.8, 54.2, 57.2, 61.1, 64.5, 66.3, 69.6], [15.0, 13.4, 11.3, 11.4, 10.0, 8.8, 8.0, 5.5], 'b-', linewidth=1.5)
        ax.plot([51.3, 51.4, 51.5, 52.3, 56.0, 61.1], [1.6, 5.2, 5.7, 7.2, 9.1, 10.0], 'b-', linewidth=1.5)
        ax.plot([62.5, 62.4, 63.3, 64.5, 68.8], [3.5, 6.9, 7.7, 8.8, 11.8], 'b-', linewidth=1.5)
        ax.plot([44.0, 51.5, 53.1, 54.4, 62.4], [5.9, 5.7, 5.7, 5.7, 6.9], 'b-', linewidth=1.5)
        ax.plot([49.3, 55.3, 56.0, 61.1], [9.3, 9.2, 9.1, 10.0], 'b-', linewidth=1.5)
        ax.plot([45.6, 52.3], [7.1, 7.2], 'b-', linewidth=1.5)
        ax.plot([51.3, 51.4, 51.5], [1.6, 5.2, 5.7], 'b-', linewidth=1.5)
        ax.plot([44.9, 47.5], [9.6, 8.6], 'b-', linewidth=1.5)
        ax.plot([54.6, 54.4], [1.7, 5.7], 'b-', linewidth=1.5)
        ax.plot([40.0, 43.0], [9.5, 8.4], 'b-', linewidth=1.5)
        ax.plot([62.5, 62.4], [3.5, 6.9], 'b-', linewidth=1.5)
        ax.plot([57.2, 61.5], [11.4, 14.1], 'b-', linewidth=1.5)
        
        ax.text(38.5, 7.0, 'Ijolite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(55.8, 13.9, 'Nepheline-syenite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(63.0, 11.7, 'Syenite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(68.8, 9.8, 'Alkaline\nGranite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(70.6, 7.3, 'Granite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(65.9, 5.5, 'Granodiorite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(57.6, 4.5, 'Diorite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(47.8, 2.5, 'Gabbro', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(44.4, 4.1, 'Gabbro', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(47.8, 6.3, 'Gabbro', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(54.1, 8.1, 'Syenodiorite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(55.5, 10.2, 'Syenite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(58.3, 7.3, 'Alkaline', fontsize=10, ha='center', va='center', rotation=20, color='g')
        ax.text(58.6, 6.6, 'Sub-alkaline', fontsize=10, ha='center', va='center', rotation=20, color='g')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None):
        cls.draw_fields(ax)
        
        default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        plotted_categories = set()
        
        for i, ((x, y), name) in enumerate(zip(data, sample_names)):
            if x is not None and y is not None:
                color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
                marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
                label = name if (show_category_legend and category_colors and name not in plotted_categories) else None
                plotted_categories.add(name)
                
                ax.scatter(x, y, marker=marker, s=80, c=[color], edgecolors='black',
                          linewidths=0.5, zorder=10, label=label)
        
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


class Cox1979_TAS:
    """Na2O + K2O vs SiO2 Cox et al. (1979) for volcanic rocks"""
    
    name = "Na2O + K2O vs SiO2"
    reference = "Cox et al. (1979) Volcanic Rocks"
    
    @classmethod
    def calculate_coordinates(cls, feature, layer):
        na = get_element_value(feature, layer, 'Na2O')
        k = get_element_value(feature, layer, 'K2O')
        si = get_element_value(feature, layer, 'SiO2')

        if na is not None and k is not None and si is not None and na > 0 and k > 0 and si > 0:
            return si, (na + k)
        return None, None

    @classmethod
    def draw_fields(cls, ax):
        ax.plot([41, 41], [1, 3], 'b-', linewidth=1.5)
        ax.plot([41, 41, 45], [3, 7, 9.4], 'b--', linewidth=1.5)
        ax.plot([45, 48.4, 52.5], [9.4, 11.5, 14], 'b-', linewidth=1.5)
        ax.plot([45, 45, 45, 49.4, 53, 57.6, 60], [1, 3, 5, 7.3, 9.3, 11.7, 12.5], 'b-', linewidth=1.5)
        ax.plot([45, 52, 57, 63, 69], [5, 5, 5.9, 7, 8], 'b-', linewidth=1.5)
        ax.plot([52, 52, 49.4, 45], [1, 5, 7.3, 9.4], 'b-', linewidth=1.5)
        ax.plot([57, 57, 53, 48.4], [1, 5.9, 9.3, 11.5], 'b-', linewidth=1.5)
        ax.plot([63, 63, 57.6, 51], [1, 7, 11.7, 14.8], 'b-', linewidth=1.5)
        ax.plot([76.5, 69, 69], [1, 8, 13], 'b-', linewidth=1.5)
        ax.plot([45, 52], [5, 5], 'b-', linewidth=1.5)
        ax.plot([41, 45], [3, 3], 'b-', linewidth=1.5)

        ax.text(43, 13, 'Foidite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(43, 2, 'Picro-\nbasalt', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(48, 3, 'Basalt', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(54.8, 3.5, 'Basaltic\nAndesite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(60, 4, 'Andesite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(67, 4.5, 'Dacite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(73, 8, 'Rhyolite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(45, 7.5, 'Tephrite\n(ol <10%)', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(43, 5.7, 'Basanite\n(ol>10%)', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(48.8, 5.5, 'Trachy-\nbasalt', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(52.7, 7.5, 'Basaltic\ntrachy-\nandesite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(58, 8, 'Trachy-\nandesite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(65, 10, 'Trachyte\n(q<20%)\n\nTrachydacite\n(q>20%)', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(48, 9.5, 'Phono-\ntephrite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(53, 12, 'Tephri-\nphonolite', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(58, 13, 'Phonolite', fontsize=12, ha='center', va='center', fontweight='bold')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True, show_category_legend=True, sample_colors=None, category_colors=None, sample_markers=None, category_markers=None, n_samples=None):
        cls.draw_fields(ax)
        
        default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        
        if sample_colors is None:
            sample_colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        plotted_categories = set()
        
        for i, ((x, y), name) in enumerate(zip(data, sample_names)):
            if x is not None and y is not None:
                color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
                marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
                label = name if (show_category_legend and category_colors and name not in plotted_categories) else None
                plotted_categories.add(name)
                
                ax.scatter(x, y, marker=marker, s=80, c=[color], edgecolors='black',
                          linewidths=0.5, zorder=10, label=label)
        
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


DISCRIMINATION_DIAGRAMS = {
    'Na2O + K2O vs SiO2 Plutonic (Wilson 1989)': Wilson1989_TAS,
    'Na2O + K2O vs SiO2 Volcanic (Cox et al 1979)': Cox1979_TAS,
    'Zr/Ti vs Nb/Y (Pearce 1996)': Pearce1996_NbY_ZrTi,
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
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setup_ui()
        self.load_layers()
        
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

        main_layout.addWidget(layer_group)

        # Tabs
        self.tab_widget = QTabWidget()

        # Tab 1: Spider Diagram
        spider_tab = QWidget()
        spider_layout = QVBoxLayout(spider_tab)
        spider_layout.setSpacing(5)

        norm_row = QHBoxLayout()
        norm_row.addWidget(QLabel("Normalize:"))
        self.norm_combo = QComboBox()
        self.norm_combo.addItems(["CI Chondrite", "Primitive Mantle"])
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

        self.tab_widget.addTab(discrim_tab, "Discrimination")

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

        # REE Normalization
        ree_group = QGroupBox("REE Normalization")
        ree_layout = QVBoxLayout(ree_group)
        ree_layout.setSpacing(2)
        self.ree_norm_group = QButtonGroup(self)
        self.ree_norm_none = QRadioButton("None")
        self.ree_norm_none.setChecked(True)
        self.ree_norm_chondrite = QRadioButton("Chondrite")
        self.ree_norm_pm = QRadioButton("Primitive Mantle")
        self.ree_norm_group.addButton(self.ree_norm_none, 0)
        self.ree_norm_group.addButton(self.ree_norm_chondrite, 1)
        self.ree_norm_group.addButton(self.ree_norm_pm, 2)
        ree_layout.addWidget(self.ree_norm_none)
        ree_layout.addWidget(self.ree_norm_chondrite)
        ree_layout.addWidget(self.ree_norm_pm)
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

        main_layout.addWidget(self.tab_widget)

        # Sample selection
        sample_group = QGroupBox("Samples")
        sample_layout = QVBoxLayout(sample_group)
        sample_layout.setSpacing(3)
        
        self.feature_list = QListWidget()
        self.feature_list.setSelectionMode(QListWidget.MultiSelection)
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
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.setWidget(scroll_area)
        self.setMinimumWidth(320)

    def load_layers(self):
        """Load vector layers into the combo box."""
        self.layer_combo.blockSignals(True)
        current_layer_id = self.layer_combo.currentData()
        self.layer_combo.clear()
        
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
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
            item.setData(Qt.UserRole, fid)
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

    def get_normalization_values(self):
        """Get normalization values."""
        if self.norm_combo.currentIndex() == 0:
            return CHONDRITE_VALUES
        return PRIMITIVE_MANTLE_VALUES

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
            fid = item.data(Qt.UserRole)
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

    def generate_spider_diagram(self, layer, features, sample_names):
        """Generate spider diagram."""
        element_order = self.get_element_order()
        norm_values = self.get_normalization_values()

        plot_data = []
        for feature in features:
            normalized_values = []
            for element in element_order:
                value = np.nan
                field_name = find_element_field(layer, element)
                if field_name:
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

        fig, ax = plt.subplots(figsize=(12, 8))
        x_positions = np.arange(len(element_order))
        
        category_colors, sample_colors, unique_categories, category_markers, sample_markers = create_categorical_color_map(sample_names)

        plotted_categories = set()
        
        for i, (values, name) in enumerate(zip(plot_data, sample_names)):
            marker = sample_markers[i] if self.spider_markers.isChecked() else None
            color = sample_colors[i]
            label = name if name not in plotted_categories else None
            plotted_categories.add(name)
            
            ax.plot(x_positions, values, marker=marker, markersize=8, linewidth=1.5,
                   label=label, color=color, markerfacecolor='white' if marker else None,
                   markeredgecolor=color, markeredgewidth=1.5)

        ax.set_yscale('log')
        ax.set_xlim(-0.5, len(element_order) - 0.5)
        ax.set_ylim(0.1, 1000)
        ax.set_xticks(x_positions)
        ax.set_xticklabels(element_order, fontsize=10)

        norm_name = "CI Chondrite" if self.norm_combo.currentIndex() == 0 else "Primitive Mantle"
        ax.set_ylabel(f'Sample / {norm_name}', fontsize=12)
        ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
        ax.yaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=10))
        ax.grid(True, which='major', axis='y', linestyle='-', alpha=0.3)
        ax.grid(True, which='minor', axis='y', linestyle=':', alpha=0.2)

        n_samples = len(plot_data)
        ax.set_title(f'Multi-Element Spider Diagram (n={n_samples})\nNormalized to {norm_name}', fontsize=14)

        if self.spider_legend.isChecked():
            n_categories = len(unique_categories)
            ncol = max(1, min(6, (n_categories + 3) // 4))
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), fontsize=9,
                     ncol=ncol, framealpha=0.9, borderaxespad=0.)
        
        plt.tight_layout()
        fig.subplots_adjust(bottom=0.25)
        plt.show()
        self.current_fig = fig

    def generate_discrimination_diagram(self, layer, features, sample_names):
        """Generate discrimination diagram."""
        diagram_name = self.diagram_combo.currentText()
        diagram_class = DISCRIMINATION_DIAGRAMS[diagram_name]

        data = []
        for feature in features:
            coords = diagram_class.calculate_coordinates(feature, layer)
            data.append(coords)

        valid_count = sum(1 for coords in data if coords[0] is not None)

        category_colors, sample_colors, unique_categories, category_markers, sample_markers = create_categorical_color_map(sample_names)

        fig, ax = plt.subplots(figsize=(10, 8))
        diagram_class.plot(ax, data, sample_names, 
                          show_legend=self.discrim_legend.isChecked(),
                          show_category_legend=self.discrim_category_legend.isChecked(),
                          sample_colors=sample_colors, category_colors=category_colors,
                          sample_markers=sample_markers, category_markers=category_markers,
                          n_samples=valid_count)
        plt.tight_layout()
        fig.subplots_adjust(bottom=0.2)
        plt.show()
        self.current_fig = fig

    def generate_custom_xy_plot(self, layer, features, sample_names):
        """Generate custom XY plot."""
        x_num = self.x_num_combo.currentText()
        x_denom = self.x_denom_combo.currentText()
        y_num = self.y_num_combo.currentText()
        y_denom = self.y_denom_combo.currentText()
        
        ree_norm_id = self.ree_norm_group.checkedId()
        norm_values = None
        norm_name = ""
        if ree_norm_id == 1:
            norm_values = CHONDRITE_VALUES
            norm_name = "CI Chondrite"
        elif ree_norm_id == 2:
            norm_values = PRIMITIVE_MANTLE_VALUES
            norm_name = "Primitive Mantle"
        
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
        
        fig, ax = plt.subplots(figsize=(12, 9))
        
        if self.x_scale_combo.currentIndex() == 1:
            ax.set_xscale('log')
        if self.y_scale_combo.currentIndex() == 1:
            ax.set_yscale('log')
        
        default_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        plotted_categories = set()
        
        for i, (x, y, name) in enumerate(zip(x_data, y_data, sample_names)):
            if x is not None and y is not None:
                color = sample_colors[i] if i < len(sample_colors) else sample_colors[i % len(sample_colors)]
                marker = sample_markers[i] if sample_markers else default_markers[i % len(default_markers)]
                
                label = None
                if self.custom_legend.isChecked() and name not in plotted_categories:
                    label = name
                    plotted_categories.add(name)
                
                if self.custom_markers.isChecked():
                    ax.scatter(x, y, marker=marker, s=80, c=[color], 
                              edgecolors='black', linewidths=0.5, zorder=10, label=label)
                else:
                    ax.scatter(x, y, s=80, c=[color], 
                              edgecolors='black', linewidths=0.5, zorder=10, label=label)
        
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
        self.current_fig = fig

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
