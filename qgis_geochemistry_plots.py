"""
QGIS Python Script: Geochemistry Plotting Tools
================================================
This script creates:
1. Chondrite-or Primitive Mantle normalized spider diagrams (REE + trace elements)
2. Tectonic discrimination diagrams:
   - Nb/Y vs Zr/Ti (Winchester & Floyd 1977; Pearce 1996)
   - Zr/4-2Nb-Y ternary (Meschede 1986)
   - Nb vs Y (Pearce et al. 1984)
   - Rb vs (Y+Nb) (Pearce et al. 1984)
   - Ti vs Zr (Pearce & Cann 1973)

Usage:
    1. Open QGIS and load your vector point layer with geochemical data
    2. Select some or all of the points (can be updated in dialog)
    3. Open the Python Console (Plugins > Python Console)
    4. Load this script and run it
    5. A dialog will appear to select your layer and configure plots
"""

import os
import sys
from qgis.core import QgsProject, QgsVectorLayer
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QListWidget, QListWidgetItem, QCheckBox,
    QFileDialog, QMessageBox, QGroupBox, QTabWidget, QWidget
)
from qgis.PyQt.QtCore import Qt

try:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    from matplotlib.patches import Polygon
    from matplotlib.lines import Line2D
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("WARNING: matplotlib not available. Install using: pip install matplotlib")


# =============================================================================
# CHONDRITE NORMALIZATION VALUES (Sun & McDonough 1989)
# =============================================================================

CHONDRITE_VALUES = {
    'Ba': 2.41, 'Rb': 2.32, 'Cs': 0.188, 'Sr': 7.26, 'K': 545, 'K2O': 0.0545,
    'Th': 0.029, 'U': 0.0074, 'Nb': 0.246, 'Ta': 0.014, 'Zr': 3.87, 'Hf': 0.1066,
    'Ti': 436, 'TiO2': 0.0728, 'P': 1220, 'P2O5': 0.28,
    'La': 0.237, 'Ce': 0.612, 'Pr': 0.095, 'Nd': 0.467, 'Sm': 0.153, 'Eu': 0.058,
    'Gd': 0.2055, 'Tb': 0.0374, 'Dy': 0.254, 'Ho': 0.0566, 'Er': 0.1655,
    'Tm': 0.0255, 'Yb': 0.170, 'Lu': 0.0254, 'Y': 1.57, 'Sc': 5.92, 'Pb': 2.47,
}

PRIMITIVE_MANTLE_VALUES = {
    'Ba': 6.6, 'Rb': 0.6, 'Cs': 0.021, 'Sr': 19.9, 'K': 240,
    'Th': 0.0795, 'U': 0.0203, 'Nb': 0.658, 'Ta': 0.037,
    'La': 0.648, 'Ce': 1.675, 'Pr': 0.254, 'Nd': 1.25, 'Sm': 0.406,
    'Eu': 0.154, 'Gd': 0.544, 'Tb': 0.099, 'Dy': 0.674, 'Ho': 0.149,
    'Er': 0.438, 'Tm': 0.068, 'Yb': 0.441, 'Lu': 0.0675, 'Y': 4.3,
    'Zr': 10.5, 'Hf': 0.283, 'Ti': 1205, 'P': 90, 'Pb': 0.15, 'Sc': 16.2,
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


# =============================================================================
# FIELD NAME MATCHING UTILITIES
# =============================================================================

def find_element_field(layer, element):
    """Find the field name in a layer that corresponds to a given element.
    
    Also handles oxide forms: Ti -> TiO2_pct, Zr -> Zr_ppm, etc.
    """
    field_names = [f.name() for f in layer.fields()]
    element_upper = element.upper()
    
    # Direct element patterns
    patterns = [
        element, element.upper(), element.lower(), element.capitalize(),
        f"{element}_ppm", f"{element.upper()}_ppm", f"{element.lower()}_ppm",
        f"{element}_PPM", f"{element.upper()}_PPM", f"{element.lower()}_PPM",
        f"{element}_ppb", f"{element.upper()}_ppb", f"{element}_PPB",
        f"{element}_pct", f"{element.upper()}_pct", f"{element}_PCT",
        f"{element}_wt", f"{element}_WT", f"{element}_wtpct", f"{element}_wt_pct",
        f"{element}(ppm)", f"{element} (ppm)", f"{element}(PPM)", f"{element}_[ppm]",
    ]
    
    # Add oxide forms for elements that are commonly reported as oxides
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

    # Fallback: check for field names starting with element
    for field_name in field_names:
        field_upper = field_name.upper()
        if field_upper.startswith(element_upper):
            remainder = field_upper[len(element_upper):]
            if remainder in ['', '_PPM', '_PPB', '_PCT', '_WT', '_WTPCT',
                           '_WT_PCT', '(PPM)', ' (PPM)', '_[PPM]', '_WT%', 'PPM', 'PPB',
                           'O2_PCT', 'O_PCT', '2O3_PCT', '2O_PCT', '2O5_PCT']:
                return field_name
    return None


# Conversion factors from oxide wt% to element ppm
OXIDE_TO_ELEMENT_PPM = {
    'TiO2': 5995,    # TiO2 wt% * 5995 = Ti ppm
    'MnO': 7745,     # MnO wt% * 7745 = Mn ppm  
    'MgO': 6030,     # MgO wt% * 6030 = Mg ppm
    'CaO': 7147,     # CaO wt% * 7147 = Ca ppm
    'Na2O': 7419,    # Na2O wt% * 7419 = Na ppm
    'K2O': 8301,     # K2O wt% * 8301 = K ppm
    'P2O5': 4364,    # P2O5 wt% * 4364 = P ppm
    'Fe2O3': 6994,   # Fe2O3 wt% * 6994 = Fe ppm
    'FeO': 7773,     # FeO wt% * 7773 = Fe ppm
}


def get_element_value(feature, layer, element, convert_to_ppm=True):
    """Get the value of an element from a feature.
    
    If convert_to_ppm is True and the field is an oxide (e.g., TiO2_pct),
    it will be converted to element ppm.
    """
    field_name = find_element_field(layer, element)
    if field_name:
        try:
            value = float(feature[field_name])
            
            # Check if we need to convert oxide wt% to element ppm
            if convert_to_ppm:
                field_upper = field_name.upper()
                
                # TiO2 -> Ti
                if 'TIO2' in field_upper and ('PCT' in field_upper or 'WT' in field_upper):
                    value = value * 5995  # TiO2 wt% to Ti ppm
                # MnO -> Mn
                elif 'MNO' in field_upper and ('PCT' in field_upper or 'WT' in field_upper):
                    value = value * 7745
                # P2O5 -> P
                elif 'P2O5' in field_upper and ('PCT' in field_upper or 'WT' in field_upper):
                    value = value * 4364
                # K2O -> K  
                elif 'K2O' in field_upper and ('PCT' in field_upper or 'WT' in field_upper):
                    value = value * 8301
                    
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
# DISCRIMINATION DIAGRAM 1: Zr/Ti vs Nb/Y (Pearce 1996)
# =============================================================================

class Pearce1996_NbY_ZrTi:
    """Nb/Y vs Zr/Ti diagram (Winchester & Floyd 1977; Pearce 1996)."""
    
    name = "Zr/Ti vs Nb/Y"
    reference = "Winchester & Floyd (1977); Pearce (1996)"

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        zr = get_element_value(feature, layer, 'Zr')
        ti = get_element_value(feature, layer, 'Ti')  # Auto-converts TiO2_pct to Ti ppm
        nb = get_element_value(feature, layer, 'Nb')
        y = get_element_value(feature, layer, 'Y')
        
        if all(v is not None and v > 0 for v in [zr, ti, nb, y]):
            return nb/y, zr/ti
        return None, None

    @classmethod
    def draw_fields(cls, ax):
        """Draw field boundaries matching the published Winchester & Floyd / Pearce diagram.
        
        Based on careful tracing of the original figure:
        - X-axis: Nb/Y from 0.01 to 10 (log scale)
        - Y-axis: Zr/Ti from 0.001 to 1 (log scale)
        """
        
        # === SUBALKALINE/ALKALINE MAIN BOUNDARY ===
        # Main diagonal line from lower-left toward upper-right
        # Starts around (0.01, 0.02) and goes to (0.67, 1)
        ax.plot([0.01, 10.0], [0.03, 0.3], 'k-', linewidth=1.0)
        
        
        # === LOWER DIAGONAL LINE ===
        # Separates basalt from andesite/basaltic andesite on subalkaline side
        # Goes from approximately (0.01, 0.002) to intersection with vertical at (0.7, 0.035)
        ax.plot([0.01, 10.0], [0.008, 0.08], 'k-', linewidth=1.0)
        
        # === RHYOLITE-DACITE / TRACHYTE BOUNDARY ===
        # Diagonal line in upper subalkaline region
        # From approximately (0.05, 1) to (0.7, 0.035)
        ax.plot([0.1, 0.7], [1.1, 0.3], 'k-', linewidth=1)
        ax.plot([0.7, 7.5], [0.3, 1.1], 'k-', linewidth=1)
        
        # === VERTICAL LINE: SUBALKALINE/ALKALINE ===
        ax.plot([0.7, 0.7], [0.3, 0.001], 'k-', linewidth=1)
        
        # === VERTICAL LINE: ALKALINE/ULTRA-ALKALINE ===
        ax.plot([3.5, 3.5], [0.72, 0.001], 'k-', linewidth=1)

        # === FIELD LABELS - SUBALKALINE ===
        ax.text(0.1, 0.006, 'Basalt', fontsize=11, ha='center', va='center')
        ax.text(0.1, 0.05, 'Andesite', fontsize=8, ha='center', va='center', style='italic',rotation=14)
        ax.text(0.1, 0.025, 'Basaltic andesite', fontsize=8, ha='center', va='center', style='italic',rotation=14)
        ax.text(0.1, 0.15, 'Rhyolite\nDacite', fontsize=10, ha='center', va='center')
        ax.text(1.8, 0.2, 'Trachyte', fontsize=10, ha='center', va='center')
        ax.text(1.8, 0.065, 'Trachy-\nandesite', fontsize=9, ha='center', va='center')
        ax.text(1.8, 0.015, 'Alkali\nBasalt', fontsize=9, ha='center', va='center')
        
        # === FIELD LABELS - ALKALINE ===
        ax.text(0.7, 0.6, 'Alkali\nRhyolite', fontsize=9, ha='center', va='center')
        ax.text(5.0, 0.4, 'Phonolite', fontsize=10, ha='center', va='center')
        ax.text(5.0, 0.09, 'Tephri-\nphonolite', fontsize=9, ha='center', va='center')
        ax.text(5.0, 0.02, 'Foidite', fontsize=10, ha='center', va='center')
    
        
        # === CLASSIFICATION LABELS ===
        ax.text(0.12, 0.0015, 'subalkaline', fontsize=9, ha='center', va='top')
        ax.text(1.8, 0.0015, 'alkaline', fontsize=9, ha='center', va='top')
        ax.text(6, 0.0015, 'ultra-\nalkaline', fontsize=8, ha='center', va='top')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        for i, ((x, y), name) in enumerate(zip(data, sample_names)):
            if x is not None and y is not None:
                ax.scatter(x, y, marker=markers[i % len(markers)],
                          s=80, c=[colors[i % 10]], edgecolors='black',
                          linewidths=0.5, zorder=10)
        
        ax.set_xlabel('Nb/Y', fontsize=12)
        ax.set_ylabel('Zr/Ti', fontsize=12)
        ax.set_title(f'{cls.name}\n{cls.reference}', fontsize=11)
        ax.set_xlim(0.01, 10)
        ax.set_ylim(0.001, 1)


# =============================================================================
# DISCRIMINATION DIAGRAM 2: Meschede 1986 Ternary
# =============================================================================

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
        """Draw Meschede 1986 field boundaries.
        
        Based on the published figure - fields are in the CENTER of the triangle,
        not spread across the whole area. The shaded region forms a roughly 
        pentagonal shape.
        
        Coordinates are (Zr/4, Y, Nb×2) and must sum to 100.
        """
        
        # === OUTER BOUNDARY OF THE FIELD AREA ===
        # This is the grey shaded polygon in the original figure
        # Tracing clockwise from the top point
        # Points are given as (Zr/4, Y, Nb×2)
        
        outer = [
            (50, 50, 0),    # Bottom point (on Zr/4-Y edge)
            (60, 29, 11),   # 
            (50, 13, 37),   # Upper left
            (13, 8, 79),   # Left side
            (23, 77, 0),   # Right Bottom point (on Zr/4-Y edge) 
        ]
        
        # Draw outer boundary as solid line
        for i in range(len(outer) - 1):
            draw_ternary_line(ax, outer[i], outer[i+1], color='k', linewidth=1.5, linestyle='-')
        
        # === INTERNAL BOUNDARIES (dashed) ===
        
        # AI / AII boundary
        draw_ternary_line(ax, (60, 29, 11), (34, 17, 49), color='k', linewidth=1, linestyle='--')
        draw_ternary_line(ax, (34, 17, 49), (17, 27, 56), color='k', linewidth=1, linestyle='--')
        
        # AII / B and AII / C boundary (the line going down from AII)
        draw_ternary_line(ax, (60, 29, 11), (38, 28, 34), color='k', linewidth=1, linestyle='--')
        draw_ternary_line(ax, (38, 28, 34), (18, 33, 49), color='k', linewidth=1, linestyle='--')
        
        # B / C boundary
        draw_ternary_line(ax, (37, 29, 34), (37, 40, 23), color='k', linewidth=1, linestyle='--')
        
        # B / D boundary  
        draw_ternary_line(ax, (21, 57, 22), (37, 40, 23), color='k', linewidth=1, linestyle='--')
        
        # C / D boundary (bottom edge)
        draw_ternary_line(ax, (52, 43, 4), (37, 40, 23), color='k', linewidth=1, linestyle='--')
        
        # === FIELD LABELS ===
        ternary_text(ax, 30, 15, 55, 'AI', fontsize=11, ha='center', va='center', fontweight='bold')
        ternary_text(ax, 35, 25, 40, 'AII', fontsize=11, ha='center', va='center', fontweight='bold')
        ternary_text(ax, 28, 37, 35, 'B', fontsize=11, ha='center', va='center', fontweight='bold')
        ternary_text(ax, 50, 35, 15, 'C', fontsize=11, ha='center', va='center', fontweight='bold')
        ternary_text(ax, 35, 55, 10, 'D', fontsize=11, ha='center', va='center', fontweight='bold')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True):
        plot_ternary_axes(ax, labels=['Zr/4', 'Y', 'Nb×2'])
        cls.draw_fields(ax)
        
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        for i, (coords, name) in enumerate(zip(data, sample_names)):
            if coords[0] is not None and coords[1] is not None and coords[2] is not None:
                x, y = ternary_to_cartesian(*coords)
                ax.scatter(x, y, marker=markers[i % len(markers)],
                          s=80, c=[colors[i % 10]], edgecolors='black',
                          linewidths=0.5, zorder=10)
        
        ax.set_title(f'{cls.name}\n{cls.reference}', fontsize=11)
        
        if show_legend:
            legend_text = "AI, AII = WP alkali basalts\nB = P-type MORB\nC = VAB\nD = N-type MORB"
            ax.text(0.9, 0.5, legend_text, transform=ax.transAxes, fontsize=8,
                   verticalalignment='center', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))


# =============================================================================
# DISCRIMINATION DIAGRAM 3: Nb vs Y (Pearce et al. 1984)
# =============================================================================

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
        """Draw Pearce et al. 1984 Nb vs Y field boundaries.
        
        Based on the published figure (B) showing:
        - VAG + syn-COLG - lower left triangular area
        - WPG (Within Plate Granites) - upper area
        - ORG (Ocean Ridge Granites) - lower right area
        
        Key points from the figure:
        - VAG+syn-COLG / WPG boundary goes through approximately (6, 3) to (60, 30) to (1000, 500)
        - VAG+syn-COLG / ORG boundary goes through approximately (25, 7) to (1000, 300)
        """
        
        # === VAG+syn-COLG / WPG BOUNDARY (upper diagonal) ===
        # This line separates the lower-left VAG+syn-COLG from the upper WPG
        # Runs from approximately (1, 1) through (25, 25) area toward upper right
        ax.plot([1, 50], [2000, 10], 'k-', linewidth=1.5)
        
        # === VAG+syn-COLG / ORG BOUNDARY (lower diagonal) ===
        # Separates VAG+syn-COLG from ORG on the right side
        # Starts from the intersection point around (25, 5-10) and goes to lower right
        ax.plot([50, 40], [10, 1], 'k-', linewidth=1.5)
        
        # === WPG / ORG BOUNDARY (lower diagonal) ===
        # Separates WPG from ORG 
        # Starts from the intersection point around (25, 5-10) and goes to lower right
        ax.plot([50, 1000], [10, 100], 'k-', linewidth=1.5)
        
        # === WPG / ORG BOUNDARY (upper diagonal) ===
        # Separates WPG from ORG 
        # Starts from the intersection point around (25, 5-10) and goes to lower right
        ax.plot([30, 1000], [20, 300], 'k--', linewidth=1.5)
        
        # === FIELD LABELS ===
        ax.text(6, 3, 'VAG +\nsyn-COLG', fontsize=12, ha='center', va='center')
        ax.text(200, 600, 'WPG', fontsize=12, ha='center', va='center')
        ax.text(200, 7, 'ORG', fontsize=12, ha='center', va='center')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        for i, ((x, y), name) in enumerate(zip(data, sample_names)):
            if x is not None and y is not None:
                ax.scatter(x, y, marker=markers[i % len(markers)],
                          s=80, c=[colors[i % 10]], edgecolors='black',
                          linewidths=0.5, zorder=10)
        
        ax.set_xlabel('Y (ppm)', fontsize=12)
        ax.set_ylabel('Nb (ppm)', fontsize=12)
        ax.set_title(f'{cls.name}\n{cls.reference}', fontsize=11)
        ax.set_xlim(1, 1000)
        ax.set_ylim(1, 2000)
        
        if show_legend:
            legend_elements = [
                Line2D([0], [0], color='w', marker='', label='VAG = Volcanic arc granites'),
                Line2D([0], [0], color='w', marker='', label='syn-COLG = Syn-collision granites'),
                Line2D([0], [0], color='w', marker='', label='WPG = Within-plate granites'),
                Line2D([0], [0], color='w', marker='', label='ORG = Ocean ridge granites'),
            ]
            ax.legend(handles=legend_elements, loc='lower right', fontsize=8, framealpha=0.9)


# =============================================================================
# DISCRIMINATION DIAGRAM 4: Rb vs (Y+Nb) (Pearce et al. 1984)
# =============================================================================

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
        """Draw Pearce et al. 1984 Rb vs (Y+Nb) field boundaries.
        
        Based on the published figure showing:
        - VAG (Volcanic Arc Granites) - lower left
        - syn-COLG (Syn-Collision Granites) - upper left  
        - WPG (Within Plate Granites) - upper right
        - ORG (Ocean Ridge Granites) - lower right
        """
        
        # === VAG / syn-COLG DIAGONAL BOUNDARY ===
        # Runs from lower-left to upper-right
        # Approximately from (1, 2) to (50, 300) based on the figure
        ax.plot([50, 50], [1, 300], 'k-', linewidth=1.5)
        
        # === syn-COLG / WPG DIAGONAL BOUNDARY ===  
        # Continues from the VAG/syn-COLG line upward
        # From (50, 300) to approximately (300, 3000)
        ax.plot([50, 400], [300, 2000], 'k-', linewidth=1.5)
        
        # === HORIZONTAL LINE: syn-COLG / VAG BOUNDARY ===
        # At Rb ~ 300, from the vertical line to the right
        ax.plot([1, 50], [80, 300], 'k-', linewidth=1.5)
        
        # === VERTICAL LINE: VAG / ORG BOUNDARY ===
        # At Y+Nb ~ 50, from bottom to the horizontal line
        ax.plot([50, 2000], [8, 400], 'k-', linewidth=1.5)
        
        # === FIELD LABELS ===
        ax.text(8, 30, 'VAG', fontsize=12, ha='center', va='center')
        ax.text(12, 700, 'syn-COLG', fontsize=11, ha='center', va='center')
        ax.text(400, 200, 'WPG', fontsize=12, ha='center', va='center')
        ax.text(400, 20, 'ORG', fontsize=12, ha='center', va='center')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True):
        ax.set_xscale('log')
        ax.set_yscale('log')
        cls.draw_fields(ax)
        
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        for i, ((x, y), name) in enumerate(zip(data, sample_names)):
            if x is not None and y is not None:
                ax.scatter(x, y, marker=markers[i % len(markers)],
                          s=80, c=[colors[i % 10]], edgecolors='black',
                          linewidths=0.5, zorder=10)
        
        ax.set_xlabel('Y + Nb (ppm)', fontsize=12)
        ax.set_ylabel('Rb (ppm)', fontsize=12)
        ax.set_title(f'{cls.name}\n{cls.reference}', fontsize=11)
        ax.set_xlim(1, 10000)
        ax.set_ylim(1, 10000)
        
        if show_legend:
            legend_elements = [
                Line2D([0], [0], color='w', marker='', label='VAG = Volcanic arc granites'),
                Line2D([0], [0], color='w', marker='', label='Syn-COLG = Syn-collision granites'),
                Line2D([0], [0], color='w', marker='', label='WPG = Within-plate granites'),
                Line2D([0], [0], color='w', marker='', label='ORG = Ocean ridge granites'),
            ]
            ax.legend(handles=legend_elements, loc='lower right', fontsize=8, framealpha=0.9)


# =============================================================================
# DISCRIMINATION DIAGRAM 5: Ti vs Zr (Pearce & Cann 1973)
# =============================================================================

class PearceCann1973_ZrTi:
    """Ti vs Zr diagram (Pearce & Cann, 1973)."""
    
    name = "Ti vs Zr"
    reference = "Pearce & Cann (1973)"

    @classmethod
    def calculate_coordinates(cls, feature, layer):
        zr = get_element_value(feature, layer, 'Zr')
        ti = get_element_value(feature, layer, 'Ti')  # Auto-converts TiO2_pct to Ti ppm
        
        if zr is not None and ti is not None and zr > 0 and ti > 0:
            return zr, ti
        return None, None

    @classmethod
    def draw_fields(cls, ax):
        """Draw Pearce & Cann 1973 Ti-Zr field boundaries.
        
        Based on the published figure showing three main fields:
        - IAT (Island Arc Tholeiites) - lower left triangular area
        - MORB + IAT + CAB - central overlap region  
        - MORB - upper right
        - CAB (Calc-Alkaline Basalts) - lower right
        """
        
        # === fields ===
        # Outer loop
        ax.plot([100, 80, 4, 19, 59, 84], [1600, 1800, 1600, 4400, 8600, 6200], 'b-', linewidth=1.5)
        # Inner Loop
        ax.plot([100, 84, 80,  44, 36, 48, 88], [7400, 6200, 5900, 3000, 3800, 5900, 9000], 'b-', linewidth=1.5)
        # IAT/CAB
        ax.plot([80, 80], [1800, 5900], 'b-', linewidth=1.5)
        
        
        
        # === FIELD LABELS ===
        ax.text(22, 2700, 'IAT', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(60, 5500, 'MORB + IAT\n+ CAB', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(87, 7500, 'MORB', fontsize=12, ha='center', va='center', fontweight='bold')
        ax.text(93, 3500, 'CAB', fontsize=12, ha='center', va='center', fontweight='bold')

    @classmethod
    def plot(cls, ax, data, sample_names, show_legend=True):
        cls.draw_fields(ax)
        
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        colors = plt.cm.tab10(np.linspace(0, 1, min(len(data), 10)))
        
        for i, ((x, y), name) in enumerate(zip(data, sample_names)):
            if x is not None and y is not None:
                ax.scatter(x, y, marker=markers[i % len(markers)],
                          s=80, c=[colors[i % 10]], edgecolors='black',
                          linewidths=0.5, zorder=10)
        
        ax.set_xlabel('Zr (ppm)', fontsize=12)
        ax.set_ylabel('Ti (ppm)', fontsize=12)
        ax.set_title(f'{cls.name}\n{cls.reference}', fontsize=11)
        ax.set_xlim(0, 110)
        ax.set_ylim(0, 9000)
        
        if show_legend:
            legend_elements = [
                Line2D([0], [0], color='w', marker='', label='IAT = Island arc tholeiites'),
                Line2D([0], [0], color='w', marker='', label='MORB = Mid-ocean ridge basalts'),
                Line2D([0], [0], color='w', marker='', label='CAB = Calc-alkaline basalts'),
            ]
            ax.legend(handles=legend_elements, loc='upper left', fontsize=8, framealpha=0.9)


# Diagram registry
DISCRIMINATION_DIAGRAMS = {
    'Zr/Ti vs Nb/Y (Pearce 1996)': Pearce1996_NbY_ZrTi,
    'Zr/4-Nb×2-Y Ternary (Meschede 1986)': Meschede1986_Ternary,
    'Nb vs Y (Pearce et al. 1984)': Pearce1984_YNb,
    'Rb vs (Y+Nb) (Pearce et al. 1984)': Pearce1984_YNbRb,
    'Ti vs Zr (Pearce & Cann 1973)': PearceCann1973_ZrTi,
}


# =============================================================================
# MAIN DIALOG CLASS
# =============================================================================

class GeochemistryDialog(QDialog):
    """Main dialog for geochemistry plotting tools."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Geochemistry Plotting Tools")
        self.setMinimumWidth(650)
        self.setMinimumHeight(600)
        self.current_fig = None
        self.setup_ui()
        self.load_layers()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Layer selection
        layer_group = QGroupBox("Layer Selection")
        layer_layout = QVBoxLayout(layer_group)

        layer_row = QHBoxLayout()
        layer_row.addWidget(QLabel("Vector Layer:"))
        self.layer_combo = QComboBox()
        self.layer_combo.currentIndexChanged.connect(self.on_layer_changed)
        layer_row.addWidget(self.layer_combo)
        layer_layout.addLayout(layer_row)

        id_row = QHBoxLayout()
        id_row.addWidget(QLabel("Sample ID Field:"))
        self.id_field_combo = QComboBox()
        self.id_field_combo.currentIndexChanged.connect(self.on_id_field_changed)
        id_row.addWidget(self.id_field_combo)
        layer_layout.addLayout(id_row)

        layout.addWidget(layer_group)

        # Tabs
        self.tab_widget = QTabWidget()

        # Tab 1: Spider Diagram
        spider_tab = QWidget()
        spider_layout = QVBoxLayout(spider_tab)

        norm_group = QGroupBox("Normalization")
        norm_layout = QVBoxLayout(norm_group)
        norm_row = QHBoxLayout()
        norm_row.addWidget(QLabel("Normalize to:"))
        self.norm_combo = QComboBox()
        self.norm_combo.addItems(["CI Chondrite (Sun & McDonough 1989)",
                                   "Primitive Mantle (Sun & McDonough 1989)"])
        norm_row.addWidget(self.norm_combo)
        norm_layout.addLayout(norm_row)
        spider_layout.addWidget(norm_group)

        order_group = QGroupBox("Element Order")
        order_layout = QVBoxLayout(order_group)
        order_row = QHBoxLayout()
        order_row.addWidget(QLabel("Preset:"))
        self.order_combo = QComboBox()
        self.order_combo.addItems([ "REE Only (La-Lu)", "Extended Spider (Ba-Yb)", "Extended Alternative"])
        order_row.addWidget(self.order_combo)
        order_layout.addLayout(order_row)
        spider_layout.addWidget(order_group)

        spider_opts = QHBoxLayout()
        self.spider_legend = QCheckBox("Show Legend")
        self.spider_legend.setChecked(True)
        self.spider_markers = QCheckBox("Show Markers")
        self.spider_markers.setChecked(True)
        spider_opts.addWidget(self.spider_legend)
        spider_opts.addWidget(self.spider_markers)
        spider_layout.addLayout(spider_opts)

        self.tab_widget.addTab(spider_tab, "Spider Diagram")

        # Tab 2: Discrimination Diagrams
        discrim_tab = QWidget()
        discrim_layout = QVBoxLayout(discrim_tab)

        discrim_group = QGroupBox("Select Diagram")
        discrim_group_layout = QVBoxLayout(discrim_group)
        self.diagram_combo = QComboBox()
        self.diagram_combo.addItems(list(DISCRIMINATION_DIAGRAMS.keys()))
        discrim_group_layout.addWidget(self.diagram_combo)
        discrim_layout.addWidget(discrim_group)

        discrim_opts = QHBoxLayout()
        self.discrim_legend = QCheckBox("Show Field Legend")
        self.discrim_legend.setChecked(True)
        discrim_opts.addWidget(self.discrim_legend)
        discrim_layout.addLayout(discrim_opts)
        discrim_layout.addStretch()

        self.tab_widget.addTab(discrim_tab, "Discrimination Diagrams")
        layout.addWidget(self.tab_widget)

        # Sample selection
        sample_group = QGroupBox("Sample Selection")
        sample_layout = QVBoxLayout(sample_group)
        self.feature_list = QListWidget()
        self.feature_list.setSelectionMode(QListWidget.MultiSelection)
        sample_layout.addWidget(self.feature_list)

        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_features)
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all_features)
        btn_row.addWidget(select_all_btn)
        btn_row.addWidget(deselect_all_btn)
        sample_layout.addLayout(btn_row)
        layout.addWidget(sample_group)

        # Buttons
        button_layout = QHBoxLayout()
        plot_btn = QPushButton("Generate Plot")
        plot_btn.clicked.connect(self.generate_plot)
        button_layout.addWidget(plot_btn)
        save_btn = QPushButton("Save Plot...")
        save_btn.clicked.connect(self.save_plot)
        button_layout.addWidget(save_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def load_layers(self):
        self.layer_combo.clear()
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
                self.layer_combo.addItem(layer.name(), layer.id())
        if self.layer_combo.count() > 0:
            self.on_layer_changed(0)

    def on_layer_changed_old(self, index):
        if index < 0:
            return
        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            return
        self.id_field_combo.clear()
        for field in layer.fields():
            self.id_field_combo.addItem(field.name())
        self.update_feature_list(layer)


    def on_layer_changed(self, index):
        if index < 0:
            return
        
        # Get layer_id using itemData instead of currentData
        layer_id = self.layer_combo.itemData(index)
        
        if layer_id is None:
            return
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is None:
            return
        self.id_field_combo.clear()
        for field in layer.fields():
            self.id_field_combo.addItem(field.name())
        self.update_feature_list(layer)
        
        
    def on_id_field_changed(self, index):
        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer:
            self.update_feature_list(layer)

    def update_feature_list_old(self, layer):
        self.feature_list.clear()
        id_field = self.id_field_combo.currentText()
        
        # Get the currently selected feature IDs in QGIS
        selected_ids = layer.selectedFeatureIds()
        
        for feature in layer.getFeatures():
            if id_field and id_field in [f.name() for f in layer.fields()]:
                label = str(feature[id_field])
            else:
                label = f"Feature {feature.id()}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, feature.id())
            self.feature_list.addItem(item)
            
            # Pre-select if this feature is selected in QGIS
            if feature.id() in selected_ids:
                item.setSelected(True)

    def update_feature_list(self, layer):
        self.feature_list.clear()
        id_field = self.id_field_combo.currentText()
        
        # Get the currently selected feature IDs in QGIS
        selected_ids = layer.selectedFeatureIds()
        
        for feature in layer.getFeatures():
            if id_field and id_field in [f.name() for f in layer.fields()]:
                label = str(feature[id_field])
            else:
                label = f"Feature {feature.id()}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, feature.id())
            self.feature_list.addItem(item)
            
            # Pre-select if this feature is selected in QGIS
            if feature.id() in selected_ids:
                item.setSelected(True)


    def update_feature_list_old(self, layer):
        self.feature_list.clear()
        id_field = self.id_field_combo.currentText()
        for feature in layer.getFeatures():
            if id_field and id_field in [f.name() for f in layer.fields()]:
                label = str(feature[id_field])
            else:
                label = f"Feature {feature.id()}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, feature.id())
            self.feature_list.addItem(item)

    def select_all_features(self):
        for i in range(self.feature_list.count()):
            self.feature_list.item(i).setSelected(True)

    def deselect_all_features(self):
        for i in range(self.feature_list.count()):
            self.feature_list.item(i).setSelected(False)

    def get_element_order(self):
        index = self.order_combo.currentIndex()
        if index == 1:
            return EXTENDED_SPIDER_ORDER
        elif index == 0:
            return REE_ORDER
        return EXTENDED_ORDER_ALT

    def get_normalization_values(self):
        if self.norm_combo.currentIndex() == 0:
            return CHONDRITE_VALUES
        return PRIMITIVE_MANTLE_VALUES

    def generate_plot(self):
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

        if self.tab_widget.currentIndex() == 0:
            self.generate_spider_diagram(layer, features, sample_names)
        else:
            self.generate_discrimination_diagram(layer, features, sample_names)

    def generate_spider_diagram(self, layer, features, sample_names):
        element_order = self.get_element_order()
        norm_values = self.get_normalization_values()

        found_elements, missing_elements = get_available_elements(layer, element_order)
        print("\n" + "="*60)
        print("SPIDER DIAGRAM - FIELD MAPPING")
        print("="*60)
        print(f"Layer: {layer.name()}")
        print(f"\nMatched fields ({len(found_elements)}):")
        for elem, field in found_elements.items():
            print(f"  {elem:6} -> {field}")
        if missing_elements:
            print(f"\nMissing elements ({len(missing_elements)}):")
            print(f"  {', '.join(missing_elements)}")
        print("="*60 + "\n")

        plot_data = []
        for feature in features:
            normalized_values = []
            for element in element_order:
                value = np.nan
                field_name = find_element_field(layer, element)
                if field_name:
                    try:
                        raw_value = float(feature[field_name])
                        if element in norm_values and norm_values[element] > 0:
                            value = raw_value / norm_values[element]
                    except (ValueError, TypeError):
                        pass
                normalized_values.append(value)
            plot_data.append(normalized_values)

        fig, ax = plt.subplots(figsize=(12, 8))
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h', '*']
        colors = plt.cm.tab10(np.linspace(0, 1, min(len(plot_data), 10)))
        x_positions = np.arange(len(element_order))

        for i, (values, name) in enumerate(zip(plot_data, sample_names)):
            marker = markers[i % len(markers)] if self.spider_markers.isChecked() else None
            color = colors[i % 10]
            ax.plot(x_positions, values, marker=marker, markersize=8, linewidth=1.5,
                   label=name, color=color, markerfacecolor='white' if marker else None,
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

        if self.spider_legend.isChecked():
            ax.legend(loc='best', fontsize=9)

        ax.set_title(f'Multi-Element Spider Diagram\nNormalized to {norm_name}', fontsize=14)
        plt.tight_layout()
        plt.show()
        self.current_fig = fig

    def generate_discrimination_diagram(self, layer, features, sample_names):
        diagram_name = self.diagram_combo.currentText()
        diagram_class = DISCRIMINATION_DIAGRAMS[diagram_name]

        # Show which fields are being matched
        print("\n" + "="*60)
        print(f"DISCRIMINATION DIAGRAM: {diagram_name}")
        print("="*60)
        
        # Check required elements
        required_elements = []
        if 'Zr/Ti' in diagram_name or 'Ti vs Zr' in diagram_name:
            required_elements = ['Zr', 'Ti', 'Nb', 'Y'] if 'Nb' in diagram_name else ['Zr', 'Ti']
        elif 'Meschede' in diagram_name:
            required_elements = ['Zr', 'Nb', 'Y']
        elif 'Nb vs Y' in diagram_name:
            required_elements = ['Nb', 'Y']
        elif 'Y+Nb' in diagram_name:
            required_elements = ['Y', 'Nb', 'Rb']
        
        print("\nField mapping:")
        for elem in required_elements:
            field = find_element_field(layer, elem)
            if field:
                print(f"  {elem:6} -> {field}")
            else:
                print(f"  {elem:6} -> NOT FOUND!")
        print()

        data = []
        for feature in features:
            coords = diagram_class.calculate_coordinates(feature, layer)
            data.append(coords)

        valid_count = 0
        for name, coords in zip(sample_names, data):
            if 'Ternary' in diagram_name:
                if coords[0] is not None:
                    print(f"  {name}: a={coords[0]:.2f}, b={coords[1]:.2f}, c={coords[2]:.2f}")
                    valid_count += 1
                else:
                    print(f"  {name}: Missing data")
            else:
                if coords[0] is not None:
                    print(f"  {name}: x={coords[0]:.4f}, y={coords[1]:.4f}")
                    valid_count += 1
                else:
                    print(f"  {name}: Missing data")
        print(f"\nValid samples: {valid_count}/{len(data)}")
        print("="*60 + "\n")

        fig, ax = plt.subplots(figsize=(10, 8))
        diagram_class.plot(ax, data, sample_names, show_legend=self.discrim_legend.isChecked())
        plt.tight_layout()
        plt.show()
        self.current_fig = fig

    def save_plot(self):
        if self.current_fig is None:
            QMessageBox.warning(self, "Warning", "Please generate a plot first.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Plot", "",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)")
        if file_path:
            self.current_fig.savefig(file_path, dpi=300, bbox_inches='tight')
            QMessageBox.information(self, "Success", f"Plot saved to:\n{file_path}")


# =============================================================================
# ENTRY POINT
# =============================================================================

def run_dialog_old():
    if not MATPLOTLIB_AVAILABLE:
        print("ERROR: matplotlib is not installed.")
        return
    dialog = GeochemistryDialog(iface.mainWindow())
    dialog.exec_()

def run_dialog():
    if not MATPLOTLIB_AVAILABLE:
        print("ERROR: matplotlib is not installed.")
        return
    
    # Make matplotlib non-blocking
    plt.ion()
    
    dialog = GeochemistryDialog(iface.mainWindow())
    dialog.show()
    
    # Use QTimer to defer the refresh until after the dialog is fully shown
    from qgis.PyQt.QtCore import QTimer
    
    def refresh_dialog():
        if dialog.layer_combo.count() > 0:
            dialog.layer_combo.setCurrentIndex(0)
            dialog.layer_combo.currentIndexChanged.emit(0)
    
    QTimer.singleShot(100, refresh_dialog)

if __name__ == '__console__' or __name__ == '__main__':
    try:
        from qgis.utils import iface
        run_dialog()
    except ImportError:
        print("This script must be run from within QGIS.")
