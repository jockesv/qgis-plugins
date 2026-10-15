"""Standalone tests for the QGIS-independent core.

Run from the plugin's parent directory:
    python3 -m unittest garmin_export.tests.test_core
Set GARMIN_MKGMAP_JAR to also run the real compile test.
"""
import math
import os
import subprocess
import tempfile
import unittest

from garmin_export.core import gpx, mkgmap, polish


def circle(cx, cy, r, n=60):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n)]


class PolishTests(unittest.TestCase):
    def test_type_parsing(self):
        p = polish.parse_type_code
        self.assertEqual(p("0x16"), 0x16)
        self.assertEqual(p("2c00"), 0x2c00)
        self.assertEqual(p(" 0X50 "), 0x50)
        self.assertEqual(p(22), 22)
        self.assertIsNone(p("zz"))
        self.assertIsNone(p(""))
        self.assertIsNone(p(None))

    def test_polygon_with_hole(self):
        outer = [(18.0, 59.0), (18.1, 59.0), (18.1, 59.1), (18.0, 59.1), (18.0, 59.0)]
        hole = [(18.02, 59.02), (18.04, 59.02), (18.04, 59.04), (18.02, 59.04)]
        text = polish.feature_text(
            polish.Feature(polish.POLYGON, 0x50, [outer, hole], "Skog; norr\n", 2))
        self.assertIn("[POLYGON]", text)
        self.assertIn("Type=0x50", text)
        self.assertIn("Label=Skog, norr", text)
        self.assertEqual(text.count("Data0="), 2)
        # lat,lon order and closing vertex removed
        self.assertIn("Data0=(59.000000,18.000000),(59.000000,18.100000)", text)
        self.assertEqual(text.splitlines()[4].count("("), 4)

    def test_degenerate_dropped(self):
        f = polish.Feature(polish.LINE, 0x16, [[(1, 1), (1, 1)]])
        self.assertEqual(polish.feature_text(f), "")
        f = polish.Feature(polish.POLYGON, 0x50, [[(1, 1), (2, 2), (1, 1)]])
        self.assertEqual(polish.feature_text(f), "")

    def test_codepage_swedish(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.mp")
            with polish.PolishWriter(path, 63240001, "Åre") as w:
                w.add(polish.Feature(polish.POINT, 0x6616, [[(13.0, 63.4)]], "Åreskutan"))
            with open(path, "rb") as fh:
                raw = fh.read()
            self.assertIn("Åreskutan".encode("cp1252"), raw)


class GpxTests(unittest.TestCase):
    def test_roundtrip(self):
        g = gpx.GpxWriter()
        g.add_waypoint(18.0, 59.0, "A & B", ele=12.5)
        g.add_track([[(18.0, 59.0), (18.1, 59.1)]], "T")
        s = g.to_string()
        self.assertIn("A &amp; B", s)
        import xml.dom.minidom
        xml.dom.minidom.parseString(s.encode("utf-8"))


JAR = os.environ.get("GARMIN_MKGMAP_JAR")


@unittest.skipUnless(JAR and mkgmap.find_java(), "needs GARMIN_MKGMAP_JAR and java")
class CompileTests(unittest.TestCase):
    def compile(self, features, d, name="t"):
        path = os.path.join(d, name + ".mp")
        with polish.PolishWriter(path, 63240001, "Test") as w:
            for f in features:
                w.add(f)
        o = mkgmap.CompileOptions()
        o.map_name = "Test"
        o.make_tdb = True
        cmd = mkgmap.build_command(mkgmap.find_java(), JAR, o, [path],
                                   os.path.join(d, "out_" + name))
        r = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return os.path.join(d, "out_" + name)

    def test_compile_all_kinds(self):
        feats = [
            polish.Feature(polish.POINT, 0x6616, [[(18.05, 59.05)]], "Topp", 2),
            polish.Feature(polish.LINE, 0x16, [[(18.0, 59.0), (18.05, 59.03), (18.1, 59.1)]], "Led", 2),
            polish.Feature(polish.POLYGON, 0x50,
                           [circle(18.05, 59.05, 0.04), circle(18.05, 59.05, 0.01)], "Skog", 2),
        ]
        with tempfile.TemporaryDirectory() as d:
            out = self.compile(feats, d)
            names = os.listdir(out)
            self.assertIn("gmapsupp.img", names)
            self.assertTrue(any(n.endswith(".tdb") for n in names))
            self.assertGreater(os.path.getsize(os.path.join(out, "gmapsupp.img")), 5000)

    def test_hole_is_respected(self):
        """A polygon with a hole must differ from one without in the output.

        Compares against a hole-less polygon: if mkgmap ignored the second Data0
        line the images would be byte-identical in size.
        """
        outer = circle(18.05, 59.05, 0.04, 200)
        hole = circle(18.05, 59.05, 0.02, 200)
        with tempfile.TemporaryDirectory() as d:
            a = self.compile([polish.Feature(polish.POLYGON, 0x50, [outer], "", 2)], d, "a")
            b = self.compile([polish.Feature(polish.POLYGON, 0x50, [outer, hole], "", 2)], d, "b")
            sa = os.path.getsize(os.path.join(a, "gmapsupp.img"))
            sb = os.path.getsize(os.path.join(b, "gmapsupp.img"))
            print("hole sizes", sa, sb)
            self.assertNotEqual(sa, sb)


if __name__ == "__main__":
    unittest.main()
