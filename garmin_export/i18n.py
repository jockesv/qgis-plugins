"""Tiny translation layer: English source strings, Swedish when QGIS runs in Swedish."""

from qgis.core import QgsSettings

SV = {
    "Export to Garmin": "Exportera till Garmin",
    "Garmin map (IMG)": "Garminkarta (IMG)",
    "GPX (waypoints / tracks)": "GPX (waypoints / spår)",
    "Layers": "Lager",
    "Export": "Exportera",
    "Layer": "Lager",
    "Geometry": "Geometri",
    "Garmin type": "Garmintyp",
    "Type field": "Typfält",
    "Label field": "Etikettfält",
    "Zoom": "Zoom",
    "Point": "Punkt",
    "Line": "Linje",
    "Polygon": "Polygon",
    "Type field holds a hex code per feature (e.g. MP_TYPE = 0x16). It overrides the fixed type.":
        "Typfältet innehåller en hexkod per objekt (t.ex. MP_TYPE = 0x16) och går före fast typ.",
    "Zoom = highest map level the feature is shown at (0 = only fully zoomed in, 3 = visible far out).":
        "Zoom = högsta kartnivå där objektet visas (0 = bara helt inzoomat, 3 = syns långt utzoomat).",
    "Map": "Karta",
    "Map name": "Kartnamn",
    "Copyright": "Copyright",
    "Family ID": "Family ID",
    "First map ID": "Första karta-ID",
    "Character set": "Teckenuppsättning",
    "Latin-1 (best compatibility)": "Latin-1 (bäst kompatibilitet)",
    "Unicode (UTF-8)": "Unicode (UTF-8)",
    "Tile width (°)": "Rutbredd (°)",
    "Tile height (°)": "Ruthöjd (°)",
    "0 = no tiling": "0 = ingen rutindelning",
    "Selected features only": "Endast markerade objekt",
    "Output": "Utdata",
    "Output folder": "Utdatamapp",
    "Only write .mp files (compile yourself)": "Skriv bara .mp-filer (kompilera själv)",
    "Also create .tdb for BaseCamp/MapSource": "Skapa även .tdb för BaseCamp/MapSource",
    "Make map searchable (--index)": "Gör kartan sökbar (--index)",
    "mkgmap": "mkgmap",
    "mkgmap.jar (or its folder)": "mkgmap.jar (eller dess mapp)",
    "Java executable (empty = from PATH)": "Java-program (tom = från PATH)",
    "TYP file (optional)": "TYP-fil (valfri)",
    "Extra mkgmap options": "Extra mkgmap-flaggor",
    "Java memory (MB)": "Java-minne (MB)",
    "Layer to export": "Lager att exportera",
    "Name field": "Namnfält",
    "Write lines as routes instead of tracks": "Skriv linjer som rutter i stället för spår",
    "GPX file": "GPX-fil",
    "Close": "Stäng",
    "Cancel": "Avbryt",
    "Choose at least one layer.": "Välj minst ett lager.",
    "Choose an output folder.": "Välj en utdatamapp.",
    "mkgmap.jar not found. Download it from mkgmap.org.uk.": "mkgmap.jar hittades inte. Ladda ner den från mkgmap.org.uk.",
    "Java not found. Install a JRE (8 or newer).": "Java hittades inte. Installera en JRE (8 eller nyare).",
    "Wrote %d features in %d tile(s).": "Skrev %d objekt i %d ruta/rutor.",
    "Skipped %d features (invalid or degenerate geometry).": "Hoppade över %d objekt (ogiltig eller degenererad geometri).",
    "%d features had no valid Garmin type and were skipped.": "%d objekt saknade giltig Garmintyp och hoppades över.",
    "Compiling with mkgmap...": "Kompilerar med mkgmap...",
    "Done. Copy gmapsupp.img to the Garmin folder on the device:": "Klart. Kopiera gmapsupp.img till mappen Garmin på enheten:",
    "mkgmap failed (exit code %d).": "mkgmap misslyckades (felkod %d).",
    "Canceled.": "Avbrutet.",
    "Choose a layer.": "Välj ett lager.",
    "Choose a GPX file.": "Välj en GPX-fil.",
    "Wrote %d waypoints, %d routes, %d tracks to %s": "Skrev %d waypoints, %d rutter, %d spår till %s",
    "Error": "Fel",
    "Information": "Information",
    "Export GIS data to Garmin GPS": "Exportera GIS-data till Garmin GPS",
}


def _is_swedish():
    try:
        loc = QgsSettings().value("locale/userLocale", "") or ""
        return str(loc).lower().startswith("sv")
    except Exception:
        return False


_SWEDISH = _is_swedish()


def tr(text):
    return SV.get(text, text) if _SWEDISH else text
