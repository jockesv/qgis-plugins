"""Minimal GPX 1.1 writer. Pure Python."""

from xml.sax.saxutils import escape

HEADER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
    '<gpx version="1.1" creator="QGIS Garmin Export" '
    'xmlns="http://www.topografix.com/GPX/1/1">\n'
)


def _ele(pt):
    return pt[2] if len(pt) > 2 else None


class GpxWriter(object):
    """Collects waypoints, tracks and routes and writes them in one go.

    Coordinates are (lon, lat) WGS84. Elevation is optional per point.
    """

    def __init__(self):
        self.waypoints = []
        self.tracks = []
        self.routes = []

    def add_waypoint(self, lon, lat, name="", ele=None, desc=""):
        self.waypoints.append((lon, lat, name, ele, desc))

    def add_track(self, segments, name=""):
        """segments: list of point lists [(lon, lat) or (lon, lat, ele), ...]."""
        segs = [s for s in segments if len(s) >= 2]
        if segs:
            self.tracks.append((name, segs))

    def add_route(self, points, name=""):
        """points: [(lon, lat) or (lon, lat, ele), ...]."""
        if len(points) >= 2:
            self.routes.append((name, points))

    @staticmethod
    def _pt(tag, lon, lat, name="", ele=None, desc=""):
        s = '<%s lat="%.7f" lon="%.7f">' % (tag, lat, lon)
        if ele is not None:
            s += "<ele>%.2f</ele>" % ele
        if name:
            s += "<name>%s</name>" % escape(name)
        if desc:
            s += "<desc>%s</desc>" % escape(desc)
        return s + "</%s>" % tag

    def to_string(self):
        out = [HEADER]
        for lon, lat, name, ele, desc in self.waypoints:
            out.append("  " + self._pt("wpt", lon, lat, name, ele, desc) + "\n")
        for name, pts in self.routes:
            out.append("  <rte>")
            if name:
                out.append("<name>%s</name>" % escape(name))
            for pt in pts:
                out.append(self._pt("rtept", pt[0], pt[1], ele=_ele(pt)))
            out.append("</rte>\n")
        for name, segs in self.tracks:
            out.append("  <trk>")
            if name:
                out.append("<name>%s</name>" % escape(name))
            for seg in segs:
                out.append("<trkseg>")
                for pt in seg:
                    out.append(self._pt("trkpt", pt[0], pt[1], ele=_ele(pt)))
                out.append("</trkseg>")
            out.append("</trk>\n")
        out.append("</gpx>\n")
        return "".join(out)

    def write(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_string())
        return (len(self.waypoints), len(self.routes), len(self.tracks))
