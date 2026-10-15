def classFactory(iface):
    from .plugin import GarminExportPlugin
    return GarminExportPlugin(iface)
