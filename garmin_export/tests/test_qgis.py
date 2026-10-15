"""Headless tests that need PyQGIS. Run with QGIS's python:

    QT_QPA_PLATFORM=offscreen python -m unittest garmin_export.tests.test_qgis
"""
import os
import subprocess
import tempfile
import unittest

from qgis.core import (QgsApplication, QgsFeature, QgsGeometry, QgsProject,
                       QgsVectorLayer, QgsPointXY)

from garmin_export import exporter
from garmin_export.core import mkgmap

_app = QgsApplication([], False)
_app.initQgis()

# Around Stockholm in SWEREF99 TM (EPSG:3006); the 20 km polygon crosses
# several cells of a 0.1-degree test grid.
BASE_X, BASE_Y = 670000.0, 6580000.0


def _read(path):
    with open(path, encoding="cp1252") as fh:
        return fh.read()


def mem_layer(geom_type, name, crs="EPSG:3006", fields="field=name:string&field=mp_type:string"):
    lyr = QgsVectorLayer("%s?crs=%s&%s" % (geom_type, crs, fields), name, "memory")
    QgsProject.instance().addMapLayer(lyr)
    return lyr


def add(lyr, geom, name="", mp_type=""):
    f = QgsFeature(lyr.fields())
    f.setGeometry(geom)
    f.setAttribute("name", name)
    f.setAttribute("mp_type", mp_type)
    lyr.dataProvider().addFeatures([f])


def poly_with_hole():
    outer = [QgsPointXY(BASE_X + dx, BASE_Y + dy)
             for dx, dy in ((0, 0), (20000, 0), (20000, 20000), (0, 20000), (0, 0))]
    hole = [QgsPointXY(BASE_X + dx, BASE_Y + dy)
            for dx, dy in ((5000, 5000), (15000, 5000), (15000, 15000), (5000, 15000), (5000, 5000))]
    return QgsGeometry.fromPolygonXY([outer, hole])


class ExporterTests(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.pts = mem_layer("Point", "pts")
        add(self.pts, QgsGeometry.fromPointXY(QgsPointXY(BASE_X + 1000, BASE_Y + 1000)), "Åkersberga")
        self.lines = mem_layer("LineString", "lines")
        add(self.lines, QgsGeometry.fromPolylineXY(
            [QgsPointXY(BASE_X, BASE_Y), QgsPointXY(BASE_X + 20000, BASE_Y + 20000)]), "Led", "0x16")
        add(self.lines, QgsGeometry.fromPolylineXY(
            [QgsPointXY(BASE_X, BASE_Y + 100), QgsPointXY(BASE_X + 500, BASE_Y + 100)]), "NoType", "")
        self.polys = mem_layer("Polygon", "polys")
        add(self.polys, poly_with_hole(), "Skog")

    def specs(self):
        return [
            exporter.LayerSpec(self.pts.id(), 0x6616, "", "name", 2),
            exporter.LayerSpec(self.lines.id(), None, "mp_type", "name", 2),
            exporter.LayerSpec(self.polys.id(), 0x50, "", "name", 2),
        ]

    def run_export(self, d, w=0.1, h=0.1):
        o = exporter.MapOptions()
        o.tile_width, o.tile_height = w, h
        return exporter.export_polish(self.specs(), o, d)

    def test_tiled_export(self):
        with tempfile.TemporaryDirectory() as d:
            files, stats = self.run_export(d)
            self.assertGreater(len(files), 1)           # crossed grid lines
            self.assertEqual(stats["no_type"], 1)      # the untyped line
            text = "".join(_read(f) for f in files)
            self.assertIn("Label=Åkersberga", text)
            self.assertIn("Type=0x6616", text)
            self.assertIn("[POLYGON]", text)
            # lat,lon order: Stockholm is ~59N, ~18E
            import re
            m = re.search(r"Data0=\((\d+\.\d+),(\d+\.\d+)\)", text)
            self.assertTrue(58 < float(m.group(1)) < 60)
            self.assertTrue(17 < float(m.group(2)) < 19)

    def test_untiled_hole_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            files, _ = self.run_export(d, 0, 0)
            self.assertEqual(len(files), 1)
            text = _read(files[0])
            poly = text[text.index("[POLYGON]"):]
            self.assertEqual(poly.count("Data0="), 2)

    def test_tiling_clips_polygon_area(self):
        """A polygon spanning several cells is split into several pieces."""
        with tempfile.TemporaryDirectory() as d:
            files, _ = self.run_export(d, 0.1, 0.05)
            n_poly = sum(_read(f).count("[POLYGON]") for f in files)
            self.assertGreater(n_poly, 1)

    def test_gpx(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.gpx")
            self.assertEqual(exporter.export_gpx(self.pts, p, "name"), (1, 0, 0))
            self.assertEqual(exporter.export_gpx(self.lines, p, "name"), (0, 0, 2))
            self.assertEqual(exporter.export_gpx(self.lines, p, "name", lines_as_routes=True), (0, 2, 0))
            self.assertEqual(exporter.export_gpx(self.polys, p, "name"), (0, 0, 1))
            with open(p, encoding="utf-8") as fh:
                self.assertIn("<gpx", fh.read())

    @unittest.skipUnless(os.environ.get("GARMIN_MKGMAP_JAR") and mkgmap.find_java(), "needs mkgmap")
    def test_compile(self):
        with tempfile.TemporaryDirectory() as d:
            files, _ = self.run_export(d, 0.1, 0.1)
            o = mkgmap.CompileOptions()
            o.make_tdb = True
            o.make_index = True
            out = os.path.join(d, "img")
            cmd = mkgmap.build_command(mkgmap.find_java(), os.environ["GARMIN_MKGMAP_JAR"], o, files, out)
            r = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(os.path.exists(os.path.join(out, "gmapsupp.img")))


class DialogTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("GARMIN_MKGMAP_JAR") and mkgmap.find_java(), "needs mkgmap")
    def test_full_run_through_dialog(self):
        from qgis.PyQt.QtCore import QEventLoop, QTimer
        from garmin_export.dialog import GarminDialog
        QgsProject.instance().clear()
        lyr = mem_layer("Point", "pts")
        add(lyr, QgsGeometry.fromPointXY(QgsPointXY(BASE_X, BASE_Y)), "A", "0x6616")
        with tempfile.TemporaryDirectory() as d:
            dlg = GarminDialog(None)
            dlg.rows[0].enabled.setChecked(True)
            dlg.out_dir.setFilePath(d)
            dlg.jar.setFilePath(os.environ["GARMIN_MKGMAP_JAR"])
            dlg._export_map()
            loop = QEventLoop()
            timer = QTimer()
            timer.setInterval(100)
            timer.timeout.connect(lambda: loop.quit() if dlg._proc is None else None)
            timer.start()
            QTimer.singleShot(60000, loop.quit)
            loop.exec()
            log = dlg.log.toPlainText()
            self.assertTrue(os.path.exists(os.path.join(d, "img", "gmapsupp.img")), log)
            self.assertIn("gmapsupp.img", log)
            dlg.close()

    def test_dialog_builds(self):
        from garmin_export.dialog import GarminDialog
        QgsProject.instance().clear()
        lyr = mem_layer("Point", "pts")
        add(lyr, QgsGeometry.fromPointXY(QgsPointXY(BASE_X, BASE_Y)), "A", "0x6616")
        dlg = GarminDialog(None)
        self.assertEqual(len(dlg.rows), 1)
        row = dlg.rows[0]
        row.enabled.setChecked(True)
        spec = row.spec()
        self.assertEqual(spec.type_field, "mp_type")   # guessed
        self.assertEqual(spec.label_field, "name")     # guessed
        self.assertEqual(spec.type_code, 0x6400)       # default for points
        row.type_combo.setEditText("0x2c0b")
        self.assertEqual(row.spec().type_code, 0x2c0b)
        row.type_combo.setEditText("junk")
        self.assertIsNone(row.spec().type_code)
        dlg._save_project_state()
        dlg2 = GarminDialog(None)
        self.assertTrue(dlg2.rows[0].enabled.isChecked())
        dlg.close()
        dlg2.close()


if __name__ == "__main__":
    unittest.main()
