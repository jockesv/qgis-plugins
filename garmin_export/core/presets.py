"""Common Garmin type codes offered in the layer table.

These are the classic codes understood by every Garmin map. Anything can be
typed by hand as hexadecimal (e.g. ``0x2c0b``); extended types above 0xff need
a matching TYP file to look right.
"""

POINT = [
    (0x6616, "Summit"),
    (0x2c00, "Attraction"),
    (0x2c0b, "Place of worship"),
    (0x2b03, "Campground"),
    (0x2b00, "Lodging"),
    (0x2a00, "Restaurant"),
    (0x2f0b, "Parking"),
    (0x6400, "Man-made place"),
    (0x6500, "Water feature"),
    (0x0100, "Large city"),
    (0x0800, "Medium city"),
    (0x0e00, "Small city"),
    (0x1100, "Village"),
]

LINE = [
    (0x16, "Trail / track"),
    (0x06, "Residential street"),
    (0x05, "Collector road"),
    (0x04, "Arterial road"),
    (0x03, "Other highway"),
    (0x02, "Principal highway"),
    (0x01, "Major highway"),
    (0x0a, "Unpaved road"),
    (0x14, "Railroad"),
    (0x18, "Stream"),
    (0x1f, "River"),
    (0x15, "Shoreline"),
    (0x20, "Contour, minor"),
    (0x21, "Contour, intermediate"),
    (0x22, "Contour, major"),
    (0x1c, "Political boundary"),
    (0x1d, "County boundary"),
    (0x1e, "International boundary"),
    (0x29, "Power line"),
]

POLYGON = [
    (0x50, "Forest / woods"),
    (0x3c, "Lake, large"),
    (0x40, "Lake, medium"),
    (0x44, "Lake, small"),
    (0x28, "Sea"),
    (0x46, "River (area)"),
    (0x51, "Wetland"),
    (0x4f, "Scrub"),
    (0x4e, "Orchard / vineyard"),
    (0x4d, "Glacier"),
    (0x01, "Urban area"),
    (0x0c, "Industrial"),
    (0x13, "Man-made area"),
    (0x0d, "Reservation"),
    (0x14, "National park"),
    (0x16, "City park"),
    (0x1e, "State park"),
    (0x18, "Golf course"),
    (0x19, "Sports complex"),
    (0x1a, "Cemetery"),
]

BY_KIND = {"point": POINT, "line": LINE, "polygon": POLYGON}

DEFAULT_TYPE = {"point": 0x6400, "line": 0x16, "polygon": 0x50}
