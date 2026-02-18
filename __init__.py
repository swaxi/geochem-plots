"""
Geochemistry Plotting Tools - QGIS Plugin
==========================================
A comprehensive geochemistry plotting tool for creating spider diagrams,
discrimination diagrams, and custom XY plots.

Developer: Mark Jessell for UWA EART3343 Lab exercises
Date: Jan 2026
"""

def classFactory(iface):
    """Load the GeochemPlottingPlugin class.
    
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .geochem_plotting import GeochemPlottingPlugin
    return GeochemPlottingPlugin(iface)
