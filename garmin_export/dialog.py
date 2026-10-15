"""The export dialog."""

import json
import os
import re

from qgis.core import QgsProject, QgsSettings, QgsVectorLayer
from qgis.gui import QgsFileWidget
from qgis.PyQt.QtCore import QProcess
from qgis.PyQt.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import exporter
from .core import mkgmap, polish, presets
from .i18n import tr

SETTINGS = "garmin_export/"
PROJECT_SCOPE = "garmin_export"
GEOM_KIND = {0: "point", 1: "line", 2: "polygon"}
KIND_TITLE = {"point": "Point", "line": "Line", "polygon": "Polygon"}
NAME_GUESS = ("name", "namn", "label", "text", "title")
TYPE_GUESS = ("mp_type", "garmin_type", "gtype", "type_code")


def _enum(cls, group, name):
    """Enum member that works with both Qt5 (unscoped) and Qt6 (scoped) PyQt."""
    scoped = getattr(cls, group, None)
    if scoped is not None and hasattr(scoped, name):
        return getattr(scoped, name)
    return getattr(cls, name)


def _vector_layers():
    out = []
    for layer in QgsProject.instance().mapLayers().values():
        if (isinstance(layer, QgsVectorLayer) and layer.isValid()
                and int(layer.geometryType()) in GEOM_KIND):
            out.append(layer)
    return sorted(out, key=lambda l: l.name().lower())


def _guess(names, candidates):
    lowered = {n.lower(): n for n in names}
    for c in candidates:
        if c in lowered:
            return lowered[c]
    return ""


def _field_combo(layer, current):
    combo = QComboBox()
    combo.addItem("", "")
    for f in layer.fields():
        combo.addItem(f.name(), f.name())
    idx = combo.findData(current)
    combo.setCurrentIndex(max(idx, 0))
    return combo


def _type_combo(kind, code):
    combo = QComboBox()
    combo.setEditable(True)
    for c, title in presets.BY_KIND[kind]:
        combo.addItem("0x%x  %s" % (c, title), c)
    if code is None:
        code = presets.DEFAULT_TYPE[kind]
    idx = combo.findData(code)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    else:
        combo.setEditText("0x%x" % code)
    return combo


def _combo_code(combo):
    """Resolve the type combo to an int code (None if empty/invalid)."""
    text = combo.currentText().strip()
    idx = combo.findText(text)
    if idx >= 0 and combo.itemData(idx) is not None:
        return combo.itemData(idx)
    m = re.match(r"(?:0x)?([0-9a-fA-F]{1,5})\b", text)
    return int(m.group(1), 16) if m else None


class LayerRow(object):
    """Widgets for one layer row, plus (de)serialisation of their state."""

    def __init__(self, layer, saved):
        self.layer = layer
        self.kind = GEOM_KIND[int(layer.geometryType())]
        names = [f.name() for f in layer.fields()]
        self.enabled = QCheckBox()
        self.enabled.setChecked(bool(saved.get("enabled", False)))
        self.type_combo = _type_combo(self.kind, saved.get("type_code"))
        self.type_field = _field_combo(
            layer, saved.get("type_field", _guess(names, TYPE_GUESS)))
        self.label_field = _field_combo(
            layer, saved.get("label_field", _guess(names, NAME_GUESS)))
        self.end_level = QSpinBox()
        self.end_level.setRange(0, 3)
        self.end_level.setValue(int(saved.get("end_level", 2)))

    def spec(self):
        return exporter.LayerSpec(
            self.layer.id(), _combo_code(self.type_combo),
            self.type_field.currentData() or "",
            self.label_field.currentData() or "", self.end_level.value())

    def state(self):
        return {
            "enabled": self.enabled.isChecked(),
            "type_code": _combo_code(self.type_combo),
            "type_field": self.type_field.currentData() or "",
            "label_field": self.label_field.currentData() or "",
            "end_level": self.end_level.value(),
        }


class GarminDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle(tr("Export GIS data to Garmin GPS"))
        self.resize(900, 700)
        self.rows = []
        self._proc = None
        self._cancel = False
        self._settings = QgsSettings()

        tabs = QTabWidget()
        tabs.addTab(self._build_map_tab(), tr("Garmin map (IMG)"))
        tabs.addTab(self._build_gpx_tab(), tr("GPX (waypoints / tracks)"))

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        buttons = QHBoxLayout()
        self.btn_export = QPushButton(tr("Export"))
        self.btn_cancel = QPushButton(tr("Cancel"))
        self.btn_cancel.setEnabled(False)
        self.btn_close = QPushButton(tr("Close"))
        buttons.addStretch()
        for b in (self.btn_export, self.btn_cancel, self.btn_close):
            buttons.addWidget(b)
        self.btn_export.clicked.connect(self._export_clicked)
        self.btn_cancel.clicked.connect(self._cancel_clicked)
        self.btn_close.clicked.connect(self.close)
        self._tabs = tabs

        lay = QVBoxLayout(self)
        lay.addWidget(tabs, 3)
        lay.addWidget(self.progress)
        lay.addWidget(self.log, 1)
        lay.addLayout(buttons)

        self._load_settings()

    # ---- building the UI -------------------------------------------------

    def _build_map_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            tr("Export"), tr("Layer"), tr("Garmin type"), tr("Type field"),
            tr("Label field"), tr("Zoom")])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, _enum(QHeaderView, "ResizeMode", "Stretch"))
        for c in (0, 2, 3, 4, 5):
            hh.setSectionResizeMode(c, _enum(QHeaderView, "ResizeMode", "ResizeToContents"))
        self.table.setToolTip(
            tr("Type field holds a hex code per feature (e.g. MP_TYPE = 0x16). "
               "It overrides the fixed type.") + "\n" +
            tr("Zoom = highest map level the feature is shown at "
               "(0 = only fully zoomed in, 3 = visible far out)."))
        lay.addWidget(self.table, 3)
        self._fill_table()

        opts = QGroupBox(tr("Map"))
        form = QFormLayout(opts)
        self.map_name = QLineEdit("Garmin Map")
        self.copyright = QLineEdit()
        self.family_id = QSpinBox()
        self.family_id.setRange(1, 65535)
        self.family_id.setValue(5001)
        self.start_id = QSpinBox()
        self.start_id.setRange(10000000, 99999000)
        self.start_id.setValue(63240001)
        self.charset = QComboBox()
        self.charset.addItem(tr("Latin-1 (best compatibility)"), 1252)
        self.charset.addItem(tr("Unicode (UTF-8)"), 65001)
        self.tile_w = QDoubleSpinBox()
        self.tile_w.setRange(0, 90)
        self.tile_w.setDecimals(3)
        self.tile_w.setValue(1.0)
        self.tile_w.setToolTip(tr("0 = no tiling"))
        self.tile_h = QDoubleSpinBox()
        self.tile_h.setRange(0, 90)
        self.tile_h.setDecimals(3)
        self.tile_h.setValue(0.5)
        self.tile_h.setToolTip(tr("0 = no tiling"))
        self.selected_only = QCheckBox(tr("Selected features only"))
        form.addRow(tr("Map name"), self.map_name)
        form.addRow(tr("Copyright"), self.copyright)
        form.addRow(tr("Family ID"), self.family_id)
        form.addRow(tr("First map ID"), self.start_id)
        form.addRow(tr("Character set"), self.charset)
        form.addRow(tr("Tile width (°)"), self.tile_w)
        form.addRow(tr("Tile height (°)"), self.tile_h)
        form.addRow("", self.selected_only)

        out = QGroupBox(tr("Output"))
        oform = QFormLayout(out)
        self.out_dir = QgsFileWidget()
        self.out_dir.setStorageMode(_enum(QgsFileWidget, "StorageMode", "GetDirectory"))
        self.only_mp = QCheckBox(tr("Only write .mp files (compile yourself)"))
        self.make_tdb = QCheckBox(tr("Also create .tdb for BaseCamp/MapSource"))
        self.make_index = QCheckBox(tr("Make map searchable (--index)"))
        self.jar = QgsFileWidget()
        self.jar.setStorageMode(_enum(QgsFileWidget, "StorageMode", "GetFile"))
        self.java = QgsFileWidget()
        self.java.setStorageMode(_enum(QgsFileWidget, "StorageMode", "GetFile"))
        self.typ = QgsFileWidget()
        self.typ.setStorageMode(_enum(QgsFileWidget, "StorageMode", "GetFile"))
        self.typ.setFilter("TYP (*.typ *.TYP *.txt)")
        self.extra = QLineEdit()
        self.memory = QSpinBox()
        self.memory.setRange(256, 32768)
        self.memory.setSingleStep(256)
        self.memory.setValue(1024)
        oform.addRow(tr("Output folder"), self.out_dir)
        oform.addRow("", self.only_mp)
        oform.addRow("", self.make_tdb)
        oform.addRow("", self.make_index)
        oform.addRow(tr("mkgmap.jar (or its folder)"), self.jar)
        oform.addRow(tr("Java executable (empty = from PATH)"), self.java)
        oform.addRow(tr("TYP file (optional)"), self.typ)
        oform.addRow(tr("Extra mkgmap options"), self.extra)
        oform.addRow(tr("Java memory (MB)"), self.memory)
        self.only_mp.toggled.connect(self._only_mp_toggled)

        side = QHBoxLayout()
        side.addWidget(opts, 1)
        side.addWidget(out, 1)
        lay.addLayout(side, 2)
        return page

    def _build_gpx_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.gpx_layer = QComboBox()
        for layer in _vector_layers():
            self.gpx_layer.addItem(layer.name(), layer.id())
        self.gpx_name = QComboBox()
        self.gpx_layer.currentIndexChanged.connect(self._gpx_layer_changed)
        self._gpx_layer_changed()
        self.gpx_selected = QCheckBox(tr("Selected features only"))
        self.gpx_routes = QCheckBox(tr("Write lines as routes instead of tracks"))
        self.gpx_file = QgsFileWidget()
        self.gpx_file.setStorageMode(_enum(QgsFileWidget, "StorageMode", "SaveFile"))
        self.gpx_file.setFilter("GPX (*.gpx)")
        form.addRow(tr("Layer to export"), self.gpx_layer)
        form.addRow(tr("Name field"), self.gpx_name)
        form.addRow("", self.gpx_selected)
        form.addRow("", self.gpx_routes)
        form.addRow(tr("GPX file"), self.gpx_file)
        return page

    def _fill_table(self):
        saved = self._project_state()
        self.rows = []
        layers = _vector_layers()
        self.table.setRowCount(len(layers))
        for r, layer in enumerate(layers):
            row = LayerRow(layer, saved.get(layer.id(), {}))
            self.rows.append(row)
            cell = QWidget()
            h = QHBoxLayout(cell)
            h.setContentsMargins(8, 0, 0, 0)
            h.addWidget(row.enabled)
            self.table.setCellWidget(r, 0, cell)
            label = QLabel("%s  [%s]" % (layer.name(), tr(KIND_TITLE[row.kind])))
            self.table.setCellWidget(r, 1, label)
            self.table.setCellWidget(r, 2, row.type_combo)
            self.table.setCellWidget(r, 3, row.type_field)
            self.table.setCellWidget(r, 4, row.label_field)
            self.table.setCellWidget(r, 5, row.end_level)

    def _gpx_layer_changed(self):
        self.gpx_name.clear()
        self.gpx_name.addItem("", "")
        layer = QgsProject.instance().mapLayer(self.gpx_layer.currentData())
        if layer is None:
            return
        names = [f.name() for f in layer.fields()]
        for n in names:
            self.gpx_name.addItem(n, n)
        guess = _guess(names, NAME_GUESS)
        if guess:
            self.gpx_name.setCurrentIndex(self.gpx_name.findData(guess))

    def _only_mp_toggled(self, on):
        for w in (self.make_tdb, self.make_index, self.jar, self.java, self.typ,
                  self.extra, self.memory):
            w.setEnabled(not on)

    # ---- persistence -----------------------------------------------------

    def _project_state(self):
        raw, ok = QgsProject.instance().readEntry(PROJECT_SCOPE, "layers", "")
        try:
            return json.loads(raw) if ok and raw else {}
        except ValueError:
            return {}

    def _save_project_state(self):
        data = {row.layer.id(): row.state() for row in self.rows}
        QgsProject.instance().writeEntry(PROJECT_SCOPE, "layers", json.dumps(data))

    def _load_settings(self):
        s = self._settings
        self.jar.setFilePath(s.value(SETTINGS + "jar", ""))
        self.java.setFilePath(s.value(SETTINGS + "java", ""))
        self.out_dir.setFilePath(s.value(SETTINGS + "out_dir", ""))
        self.map_name.setText(s.value(SETTINGS + "map_name", "Garmin Map"))
        self.family_id.setValue(int(s.value(SETTINGS + "family_id", 5001)))
        self.memory.setValue(int(s.value(SETTINGS + "memory", 1024)))

    def _save_settings(self):
        s = self._settings
        s.setValue(SETTINGS + "jar", self.jar.filePath())
        s.setValue(SETTINGS + "java", self.java.filePath())
        s.setValue(SETTINGS + "out_dir", self.out_dir.filePath())
        s.setValue(SETTINGS + "map_name", self.map_name.text())
        s.setValue(SETTINGS + "family_id", self.family_id.value())
        s.setValue(SETTINGS + "memory", self.memory.value())

    # ---- running ---------------------------------------------------------

    def _say(self, msg):
        self.log.appendPlainText(msg)
        QApplication.processEvents()

    def _set_busy(self, busy):
        self.btn_export.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)
        self._tabs.setEnabled(not busy)

    def _fail(self, msg):
        self._say(msg)
        QMessageBox.warning(self, tr("Error"), msg)

    def _cancel_clicked(self):
        self._cancel = True
        if self._proc is not None:
            self._proc.kill()

    def _progress(self, frac, _msg=""):
        self.progress.setValue(int(frac * 1000))
        QApplication.processEvents()

    def _export_clicked(self):
        if self._tabs.currentIndex() == 0:
            self._export_map()
        else:
            self._export_gpx()

    def _export_gpx(self):
        layer = QgsProject.instance().mapLayer(self.gpx_layer.currentData())
        if layer is None:
            return self._fail(tr("Choose a layer."))
        path = self.gpx_file.filePath().strip()
        if not path:
            return self._fail(tr("Choose a GPX file."))
        if not path.lower().endswith(".gpx"):
            path += ".gpx"
        try:
            w, r, t = exporter.export_gpx(
                layer, path, self.gpx_name.currentData() or "",
                self.gpx_selected.isChecked(), self.gpx_routes.isChecked())
        except Exception as e:  # report any export problem to the user
            return self._fail(str(e))
        self._say(tr("Wrote %d waypoints, %d routes, %d tracks to %s") % (w, r, t, path))

    def _export_map(self):
        specs = [row.spec() for row in self.rows if row.enabled.isChecked()]
        if not specs:
            return self._fail(tr("Choose at least one layer."))
        out_dir = self.out_dir.filePath().strip()
        if not out_dir:
            return self._fail(tr("Choose an output folder."))

        java = jar = None
        if not self.only_mp.isChecked():
            java = mkgmap.find_java(self.java.filePath().strip())
            if not java:
                return self._fail(tr("Java not found. Install a JRE (8 or newer)."))
            jar = mkgmap.find_mkgmap_jar(self.jar.filePath().strip())
            if not jar:
                return self._fail(tr("mkgmap.jar not found. Download it from mkgmap.org.uk."))

        opts = exporter.MapOptions()
        opts.map_name = self.map_name.text().strip() or "Garmin Map"
        opts.copyright = self.copyright.text().strip()
        opts.start_map_id = self.start_id.value()
        opts.codepage = self.charset.currentData()
        opts.tile_width = self.tile_w.value()
        opts.tile_height = self.tile_h.value()
        opts.selected_only = self.selected_only.isChecked()

        self._save_settings()
        self._save_project_state()
        self._cancel = False
        self._set_busy(True)
        self.log.clear()
        mp_dir = os.path.join(out_dir, "mp")
        try:
            files, stats = exporter.export_polish(
                specs, opts, mp_dir, log=self._say, progress=self._progress,
                canceled=lambda: self._cancel)
        except Exception as e:  # ExportError or an unexpected QGIS failure
            self._set_busy(False)
            return self._fail(str(e))
        self._say(tr("Wrote %d features in %d tile(s).") % (stats["written"], len(files)))
        if stats["skipped"]:
            self._say(tr("Skipped %d features (invalid or degenerate geometry).") % stats["skipped"])
        if stats["no_type"]:
            self._say(tr("%d features had no valid Garmin type and were skipped.") % stats["no_type"])

        if self.only_mp.isChecked():
            self._say(mp_dir)
            self._set_busy(False)
            return

        copts = mkgmap.CompileOptions()
        copts.map_name = opts.map_name
        copts.family_id = self.family_id.value()
        copts.start_map_id = opts.start_map_id
        copts.codepage = opts.codepage
        copts.make_tdb = self.make_tdb.isChecked()
        copts.make_index = self.make_index.isChecked()
        copts.typ_file = self.typ.filePath().strip()
        copts.extra_args = self.extra.text()
        copts.memory_mb = self.memory.value()
        self._img_dir = os.path.join(out_dir, "img")
        os.makedirs(self._img_dir, exist_ok=True)
        cmd = mkgmap.build_command(java, jar, copts, files, self._img_dir)
        self._say(tr("Compiling with mkgmap..."))
        self.progress.setRange(0, 0)  # busy indicator

        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(_enum(QProcess, "ProcessChannelMode", "MergedChannels"))
        self._proc.readyRead.connect(self._proc_output)
        self._proc.finished.connect(self._proc_finished)
        self._proc.start(cmd[0], cmd[1:])

    def _proc_output(self):
        data = bytes(self._proc.readAll()).decode("utf-8", "replace")
        for line in data.splitlines():
            if line.strip():
                self.log.appendPlainText(line)

    def _proc_finished(self, code, _status):
        self.progress.setRange(0, 1000)
        self.progress.setValue(1000 if code == 0 else 0)
        self._proc = None
        self._set_busy(False)
        if self._cancel:
            self._say(tr("Canceled."))
        elif code == 0:
            self._say(tr("Done. Copy gmapsupp.img to the Garmin folder on the device:"))
            self._say(os.path.join(self._img_dir, "gmapsupp.img"))
        else:
            self._say(tr("mkgmap failed (exit code %d).") % code)

    def closeEvent(self, event):
        if self._proc is not None:
            self._proc.kill()
        self._save_project_state()
        super().closeEvent(event)
