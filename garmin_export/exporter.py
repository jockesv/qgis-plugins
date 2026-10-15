"""QGIS-side export: reads project layers, reprojects to WGS84, tiles and
hands plain coordinate lists to the pure-Python writers in ``core``."""

import math
import os

from qgis.core import (
    NULL,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProject,
    QgsRectangle,
)

from .core import polish
from .core.gpx import GpxWriter
from .core.polish import Feature, PolishWriter, parse_type_code

KIND_BY_GEOMTYPE = {0: polish.POINT, 1: polish.LINE, 2: polish.POLYGON}
MAX_TILES = 400


class ExportError(Exception):
    pass


class LayerSpec(object):
    def __init__(self, layer_id, type_code=None, type_field="", label_field="",
                 end_level=2):
        self.layer_id = layer_id
        self.type_code = type_code      # fallback / fixed type, int or None
        self.type_field = type_field    # per-feature type code field (MP_TYPE)
        self.label_field = label_field
        self.end_level = end_level


class MapOptions(object):
    def __init__(self):
        self.map_name = "Garmin Map"
        self.copyright = ""
        self.start_map_id = 63240001
        self.codepage = 1252
        self.tile_width = 1.0     # degrees of longitude, 0 = no tiling
        self.tile_height = 0.5
        self.selected_only = False
        self.file_prefix = "map"


def _wgs84_transform(layer):
    dst = QgsCoordinateReferenceSystem("EPSG:4326")
    return QgsCoordinateTransform(layer.crs(), dst, QgsProject.instance())


def _text(value):
    if value is None or value == NULL:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _pts(curve):
    return [(p.x(), p.y()) for p in curve.points()]


def _rings(geom, dim):
    """Yield one ring list per output object for geometry parts of dimension
    ``dim``: points -> [[(x,y)]], lines -> [pts], polygons -> [exterior, *holes]."""
    if geom is None or geom.isNull() or geom.isEmpty():
        return
    for part in geom.constParts():
        if part.dimension() != dim:
            continue
        if dim == 2:
            rings = [_pts(part.exteriorRing())]
            rings += [_pts(part.interiorRing(i)) for i in range(part.numInteriorRings())]
            yield rings
        elif dim == 1:
            yield [_pts(part)]
        else:
            yield [[(part.x(), part.y())]]


def _prepare_geometry(feature, xform):
    geom = feature.geometry()
    if geom is None or geom.isNull() or geom.isEmpty():
        return None
    geom = QgsGeometry(geom)
    if geom.transform(xform) != 0:
        return None
    if geom.type() != 0 and geom.constGet().hasCurvedSegments():
        geom.convertToStraightSegment()
    return geom


def _request(layer, fields):
    req = QgsFeatureRequest()
    names = [f for f in fields if f and layer.fields().indexFromName(f) >= 0]
    req.setSubsetOfAttributes(names, layer.fields())
    return req


def _features(layer, fields, selected_only):
    if selected_only:
        return layer.getSelectedFeatures(_request(layer, fields)), layer.selectedFeatureCount()
    return layer.getFeatures(_request(layer, fields)), layer.featureCount()


def export_polish(specs, options, out_dir, log=None, progress=None, canceled=None):
    """Write one .mp per tile into ``out_dir``. Returns (files, stats)."""
    log = log or (lambda m: None)
    progress = progress or (lambda f, m="": None)
    canceled = canceled or (lambda: False)

    project = QgsProject.instance()
    layers = []
    extent = None
    for spec in specs:
        layer = project.mapLayer(spec.layer_id)
        if layer is None:
            continue
        xform = _wgs84_transform(layer)
        layers.append((spec, layer, xform))
        box = xform.transformBoundingBox(layer.extent())
        if extent is None:
            extent = QgsRectangle(box)
        else:
            extent.combineExtentWith(box)
    if not layers:
        raise ExportError("No layers selected.")

    tiling = options.tile_width > 0 and options.tile_height > 0
    if tiling:
        nx = math.floor(extent.xMaximum() / options.tile_width) - math.floor(extent.xMinimum() / options.tile_width) + 1
        ny = math.floor(extent.yMaximum() / options.tile_height) - math.floor(extent.yMinimum() / options.tile_height) + 1
        if nx * ny > MAX_TILES:
            raise ExportError("The data would need %d tiles (max %d). Use larger tiles."
                              % (nx * ny, MAX_TILES))
        log("Tiling: up to %d x %d cells of %g x %g degrees" % (nx, ny, options.tile_width, options.tile_height))

    os.makedirs(out_dir, exist_ok=True)
    writers = {}
    stats = {"written": 0, "skipped": 0, "no_type": 0}

    def writer_for(cell):
        w = writers.get(cell)
        if w is None:
            n = len(writers)
            path = os.path.join(out_dir, "%s_%04d.mp" % (options.file_prefix, n + 1))
            w = PolishWriter(path, options.start_map_id + n, options.map_name,
                             options.copyright, options.codepage)
            writers[cell] = w
        return w

    try:
        for li, (spec, layer, xform) in enumerate(layers):
            kind = KIND_BY_GEOMTYPE.get(int(layer.geometryType()))
            if kind is None:
                log("Skipping %s: unsupported geometry type" % layer.name())
                continue
            dim = {polish.POINT: 0, polish.LINE: 1, polish.POLYGON: 2}[kind]
            it, total = _features(layer, (spec.type_field, spec.label_field), options.selected_only)
            total = max(total, 1)
            log("%s: %d features" % (layer.name(), total))
            for fi, feat in enumerate(it):
                if fi % 200 == 0:
                    progress((li + fi / float(total)) / len(layers), layer.name())
                    if canceled():
                        raise ExportError("Canceled.")
                code = None
                if spec.type_field:
                    code = parse_type_code(_text(feat[spec.type_field]))
                if code is None:
                    code = spec.type_code
                if code is None:
                    stats["no_type"] += 1
                    continue
                label = _text(feat[spec.label_field]) if spec.label_field else ""

                geom = _prepare_geometry(feat, xform)
                if geom is None:
                    stats["skipped"] += 1
                    continue
                for cell, piece in _tiles(geom, dim, options, tiling):
                    for rings in _rings(piece, dim):
                        f = Feature(kind, code, rings, label, spec.end_level)
                        if writer_for(cell).add(f):
                            stats["written"] += 1
                        else:
                            stats["skipped"] += 1
    finally:
        files = []
        for w in writers.values():
            w.close()
            files.append(w.path)
    progress(1.0, "")
    if not files:
        raise ExportError("Nothing was exported (no features with a Garmin type?).")
    return sorted(files), stats


def _tiles(geom, dim, options, tiling):
    """Yield (cell, geometry) pieces of ``geom`` per tile."""
    if not tiling:
        yield (0, 0), geom
        return
    w, h = options.tile_width, options.tile_height
    if dim == 0:
        p = geom.asPoint() if not geom.isMultipart() else None
        if p is not None:
            yield (math.floor(p.x() / w), math.floor(p.y() / h)), geom
            return
    box = geom.boundingBox()
    ix0, ix1 = math.floor(box.xMinimum() / w), math.floor(box.xMaximum() / w)
    iy0, iy1 = math.floor(box.yMinimum() / h), math.floor(box.yMaximum() / h)
    if ix0 == ix1 and iy0 == iy1:
        yield (ix0, iy0), geom
        return
    if not geom.isGeosValid():
        fixed = geom.makeValid()
        if fixed is not None and not fixed.isNull():
            geom = fixed
    for ix in range(ix0, ix1 + 1):
        for iy in range(iy0, iy1 + 1):
            rect = QgsGeometry.fromRect(QgsRectangle(ix * w, iy * h, (ix + 1) * w, (iy + 1) * h))
            piece = geom.intersection(rect)
            if piece is not None and not piece.isNull() and not piece.isEmpty():
                yield (ix, iy), piece


def export_gpx(layer, path, name_field="", selected_only=False, lines_as_routes=False):
    """Write one layer to a GPX file. Returns (waypoints, routes, tracks)."""
    xform = _wgs84_transform(layer)
    kind = KIND_BY_GEOMTYPE.get(int(layer.geometryType()))
    if kind is None:
        raise ExportError("Unsupported geometry type.")
    gpx = GpxWriter()
    it, _total = _features(layer, (name_field,), selected_only)
    for feat in it:
        geom = _prepare_geometry(feat, xform)
        if geom is None:
            continue
        name = _text(feat[name_field]) if name_field else ""
        if kind == polish.POINT:
            for part in geom.constParts():
                ele = part.z() if part.is3D() and not math.isnan(part.z()) else None
                gpx.add_waypoint(part.x(), part.y(), name, ele)
            continue
        segments = []
        for part in geom.constParts():
            if kind == polish.LINE:
                curves = [part]
            else:  # polygon: outlines as tracks
                curves = [part.exteriorRing()] + [part.interiorRing(i) for i in range(part.numInteriorRings())]
            for c in curves:
                segments.append([(p.x(), p.y(), p.z()) if c.is3D() and not math.isnan(p.z())
                                 else (p.x(), p.y()) for p in c.points()])
        if kind == polish.LINE and lines_as_routes:
            for seg in segments:
                gpx.add_route(seg, name)
        else:
            gpx.add_track(segments, name)
    return gpx.write(path)
