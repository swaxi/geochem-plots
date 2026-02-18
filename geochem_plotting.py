"""
Geochemistry Plotting Tools - Main Plugin Class
================================================
Handles plugin initialization, toolbar/menu creation, and dock widget management.
"""

import os
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QAction, QDockWidget
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsApplication
from qgis.PyQt.QtWidgets import  QMessageBox

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
from .geochem_dock import GeochemistryDockWidget


class GeochemPlottingPlugin:
    """QGIS Plugin Implementation for Geochemistry Plotting Tools."""

    def __init__(self, iface):
        """Constructor.
        
        :param iface: An interface instance that provides access to QGIS
            application components.
        :type iface: QgsInterface
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = '&Geochemistry Plotting'
        self.toolbar = self.iface.addToolBar('Geochemistry Plotting')
        self.toolbar.setObjectName('GeochemistryPlottingToolbar')
        self.dock_widget = None
        self.pluginIsActive = False

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        """Add a toolbar icon and menu item.
        
        :param icon_path: Path to the icon for this action.
        :param text: Text shown in menu and as tooltip.
        :param callback: Function to call when action is triggered.
        :param enabled_flag: Enable/disable the action.
        :param add_to_menu: Flag to add action to menu.
        :param add_to_toolbar: Flag to add action to toolbar.
        :param status_tip: Status bar message.
        :param whats_this: What's This help text.
        :param parent: Parent widget.
        :returns: The action that was created.
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        
        # If icon doesn't exist, use a default QGIS icon
        if not os.path.exists(icon_path):
            icon_path = QgsApplication.iconPath('mActionShowAllLayers.svg')
        
        self.add_action(
            icon_path,
            text='Geochemistry Plotting Tools',
            callback=self.run,
            parent=self.iface.mainWindow(),
            status_tip='Open Geochemistry Plotting Tools',
            whats_this='Create spider diagrams, discrimination diagrams, and custom XY plots'
        )

    def onClosePlugin(self):
        """Cleanup necessary items when plugin dock widget is closed."""
        # Disconnect signals
        if self.dock_widget:
            self.dock_widget.closingPlugin.disconnect(self.onClosePlugin)
        self.pluginIsActive = False

    def unload(self):
        """Remove the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu('&Geochemistry Plotting', action)
            self.iface.removeToolBarIcon(action)
        
        # Remove the toolbar
        del self.toolbar
        
        # Remove dock widget
        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget = None

    def run(self):
        """Run method that loads and shows the dockable widget."""
        if not self.pluginIsActive:
            self.pluginIsActive = True
            
            # Create the dock widget if it doesn't exist
            if self.dock_widget is None:
                self.dock_widget = GeochemistryDockWidget(self.iface)
                self.dock_widget.closingPlugin.connect(self.onClosePlugin)
            
            # Add dock widget to QGIS interface
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
            right_docks = [
                d
                for d in self.iface.mainWindow().findChildren(QDockWidget)
                if self.iface.mainWindow().dockWidgetArea(d) == RightDockWidgetArea
            ]
            # If there are other dock widgets, tab this one with the first one found
            if right_docks:
                for dock in right_docks:
                    if dock != self.dock_widget:
                        self.iface.mainWindow().tabifyDockWidget(dock, self.dock_widget)
                        # Optionally, bring your plugin tab to the front
                        self.dock_widget.raise_()
                        break
            # Raise the docked widget above others
            self.dock_widget.show()
        
        # Show the dock widget
        self.dock_widget.show()
