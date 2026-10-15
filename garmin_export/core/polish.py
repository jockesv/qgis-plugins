"""Writer for the Polish Format (.mp) text format used by cGPSmapper and mkgmap.

Pure Python, no QGIS dependency. Coordinates are given as (lon, lat) tuples in
WGS84 degrees, as everywhere else in the plugin; the format itself wants (lat,lon).
"""

import re

POINT = "point"
LINE = "line"
POLYGON = "polygon"

SECTION = {POINT: "POI", LINE: "POLYLINE", POLYGON: "POLYGON"}

# Garmin zoom levels (bits per coordinate). Level N is shown up to EndLevel N.
DEFAULT_LEVELS = (24, 22, 20, 18)

_CODEPAGES = {1252: "cp1252", 65001: "utf-8"}
_LBLCODING = {1252: 9, 65001: 10}


class Feature(object):
    """One Garmin map object.

    rings: for POINT a list with one 1-tuple-ring ``[[(lon, lat)]]``, for LINE a
    list of one ring, for POLYGON the exterior ring followed by any holes.
    """

    __slots__ = ("kind", "type_code", "label", "end_level", "rings")

    def __init__(self, kind, type_code, rings, label="", end_level=2):
        self.kind = kind
        self.type_code = type_code
        self.rings = rings
        self.label = label
        self.end_level = end_level


def parse_type_code(value):
    """Parse a Garmin type code. Always hexadecimal, with or without 0x.

    Returns an int, or None if the value cannot be interpreted.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    text = str(value).strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    if not re.fullmatch(r"[0-9a-f]{1,5}", text):
        return None
    return int(text, 16)


def clean_label(text):
    """Make a label safe for the Polish format (single line, no comment char)."""
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"[\r\n\t]+", " ", text).replace(";", ",")
    return text.strip()[:250]


def _fmt_point(lon, lat):
    return "(%.6f,%.6f)" % (lat, lon)


def clean_ring(ring, kind):
    """Drop consecutive duplicates (after rounding) and the closing vertex of a
    polygon ring. Returns None if too few vertices remain."""
    out = []
    for lon, lat in ring:
        pt = (round(lon, 6), round(lat, 6))
        if not out or out[-1] != pt:
            out.append(pt)
    if kind == POLYGON:
        if len(out) > 1 and out[0] == out[-1]:
            out.pop()
        return out if len(out) >= 3 else None
    if kind == LINE:
        return out if len(out) >= 2 else None
    return out[:1] or None


def header_text(map_id, name, copyright_text="", codepage=1252, levels=DEFAULT_LEVELS):
    lines = [
        "[IMG ID]",
        "ID=%d" % map_id,
        "Name=%s" % clean_label(name),
    ]
    if copyright_text:
        lines.append("Copyright=%s" % clean_label(copyright_text))
    lines += [
        "CodePage=%d" % codepage,
        "LblCoding=%d" % _LBLCODING.get(codepage, 9),
        "Datum=W84",
        "Elevation=M",
        "Preprocess=F",
        "TreSize=3000",
        "RgnLimit=1024",
        "Levels=%d" % len(levels),
    ]
    for i, bits in enumerate(levels):
        lines.append("Level%d=%d" % (i, bits))
    lines.append("[END-IMG ID]")
    return "\n".join(lines) + "\n\n"


def feature_text(feat):
    rings = []
    for ring in feat.rings:
        cleaned = clean_ring(ring, feat.kind)
        # A hole that degenerates is simply dropped; a degenerate exterior
        # (first ring) drops the whole feature.
        if cleaned is None:
            if not rings:
                return ""
            continue
        rings.append(cleaned)
    if not rings:
        return ""

    out = ["[%s]" % SECTION[feat.kind], "Type=0x%x" % feat.type_code]
    label = clean_label(feat.label)
    if label:
        out.append("Label=%s" % label)
    out.append("EndLevel=%d" % feat.end_level)
    if feat.kind == POINT:
        out.append("Data0=%s" % _fmt_point(*rings[0][0]))
    elif feat.kind == LINE:
        out.append("Data0=%s" % ",".join(_fmt_point(*p) for p in rings[0]))
    else:  # polygon: exterior first, then holes, one Data0 line each
        for ring in rings:
            out.append("Data0=%s" % ",".join(_fmt_point(*p) for p in ring))
    out.append("[END]")
    return "\n".join(out) + "\n\n"


class PolishWriter(object):
    """Streams features to one .mp file."""

    def __init__(self, path, map_id, name, copyright_text="", codepage=1252,
                 levels=DEFAULT_LEVELS):
        self.path = path
        self.count = 0
        self._codec = _CODEPAGES.get(codepage, "cp1252")
        self._fh = open(path, "w", encoding=self._codec, errors="replace",
                        newline="\r\n")
        self._fh.write(header_text(map_id, name, copyright_text, codepage, levels))

    def add(self, feat):
        text = feature_text(feat)
        if text:
            self._fh.write(text)
            self.count += 1
            return True
        return False

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
