import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .i18n import tr


class GarminExportPlugin(object):
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
        self.action = QAction(icon, tr("Export to Garmin"), self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(tr("Export to Garmin"), self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu(tr("Export to Garmin"), self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self):
        from .dialog import GarminDialog  # lazy: keeps QGIS startup cheap

        # A fresh dialog each time so the layer list reflects the current project.
        if self.dialog is not None:
            self.dialog.close()
        self.dialog = GarminDialog(self.iface, self.iface.mainWindow())
        self.dialog.show()
