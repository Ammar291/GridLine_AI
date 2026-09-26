"""Zone label anchors that keep clear of map markers, water and lines.

The dashboard draws markers and labels at a fixed pixel size, so their footprint in map units depends on the
zoom. Anchors are chosen for the fit-to-panel view on a 1080p projector (``LABEL_UNITS_PER_PX``): each label
box must sit inside its zone and should miss every marker, the lake and the rivers; among the clear spots the
one nearest the zone centre wins. The search is a plain grid scan, deterministic and fast for ten zones.
"""

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from gridline.api.map_geometry import XY, Point, path_points, point_in_polygon, sample_polyline

if TYPE_CHECKING:
    from gridline.api.city_map import CityMap

# The fit view of the 1200x900 map in the ~450 px tall 1080p map panel draws about 2.0 units per px;
# planning at 1.8 keeps every zone solvable (Market Ward is tight) and labels clear from the first zoom step.
LABEL_UNITS_PER_PX = 1.8
CHAR_PX = 7.2  # average advance of the 13 px zone-name face
NAME_ABOVE_PX = 11  # the name's baseline is the anchor; the band line sits below it
BAND_BELOW_PX = 17
GLYPH_PX = 10  # half-size of a drawn marker glyph (project, hospital, shelter, crew, depot)
SMALL_GLYPH_PX = 6  # sensor dots and bridge ticks
MARKER_TEXT_PX = 14  # crews and the pump depot print a short label to the right of the glyph
EDGE_PX = 4  # keep this far inside the zone
SCAN_STEP = 8.0

Box = tuple[float, float, float, float]  # x0, y0, x1, y1 in map units


class Placed(Protocol):
    @property
    def xy(self) -> XY: ...


def label_box(name: str, anchor: XY, u: float) -> Box:
    half = (len(name) * CHAR_PX + 6) / 2 * u
    return anchor.x - half, anchor.y - NAME_ABOVE_PX * u, anchor.x + half, anchor.y + BAND_BELOW_PX * u


def _marker(xy: XY, u: float, half: float = GLYPH_PX, *, text: bool = False) -> Box:
    right = half + (MARKER_TEXT_PX if text else 0)
    return xy.x - half * u, xy.y - half * u, xy.x + right * u, xy.y + half * u


def glyph_boxes(city_map: "CityMap", u: float) -> list[Box]:
    """Drawn footprints of the icon markers (projects, hospitals, shelters, crews, pump depot)."""
    glyphs: list[Placed] = [*city_map.projects, *city_map.hospitals, *city_map.shelters]
    return [
        *(_marker(p.xy, u) for p in glyphs),
        *(_marker(c.xy, u, text=True) for c in city_map.crews),
        _marker(city_map.pump_depot.xy, u, text=True),
    ]


def dot_boxes(city_map: "CityMap", u: float) -> list[Box]:
    """Drawn footprints of the small markers (sensor dots, bridge ticks), with a little margin."""
    small: list[Placed] = [*city_map.sensors, *city_map.bridges]
    return [_marker(p.xy, u, SMALL_GLYPH_PX) for p in small]


def _overlaps(a: Box, b: Box) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _covered(a: Box, b: Box) -> float:
    """Share of ``b`` that ``a`` covers."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h) / ((b[2] - b[0]) * (b[3] - b[1]))


def _inside(p: Point, box: Box) -> bool:
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def place_label(
    name: str,
    zone: Box,
    *,
    glyphs: Sequence[Box],
    dots: Sequence[Box],
    lakes: Sequence[Sequence[Point]],
    river_points: Sequence[Point],
    line_points: Sequence[Point],
    u: float = LABEL_UNITS_PER_PX,
) -> XY:
    """The best anchor for ``name`` inside ``zone``: fewest collisions first, then nearest the zone centre.

    Covering an icon or the lake is ruled out whenever any spot avoids it; a sensor dot or bridge tick is only
    grazed when the zone leaves no room (the least-covered spot wins).
    """
    zx0, zy0, zx1, zy1 = zone
    cx, cy = (zx0 + zx1) / 2, (zy0 + zy1) / 2
    probe = label_box(name, XY(x=0, y=0), u)
    edge = EDGE_PX * u
    xs = _scan(zx0 + edge - probe[0], zx1 - edge - probe[2])
    ys = _scan(zy0 + edge - probe[1], zy1 - edge - probe[3])
    glyphs = [m for m in glyphs if _overlaps(m, zone)]
    dots = [m for m in dots if _overlaps(m, zone)]
    lakes = [lake for lake in lakes if any(_inside(p, zone) for p in lake)]
    river_points = [p for p in river_points if _inside(p, zone)]
    line_points = [p for p in line_points if _inside(p, zone)]
    best: tuple[float, XY] | None = None
    for x in xs:
        for y in ys:
            box = label_box(name, XY(x=x, y=y), u)
            corners = [(box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3]), (x, y)]
            score = (
                1000 * sum(_overlaps(box, m) for m in glyphs)
                + 300 * sum(_covered(box, m) for m in dots)
                + 1000 * sum(any(point_in_polygon(c, lake) for c in corners) for lake in lakes)
                + 1000 * sum(_inside(p, box) for lake in lakes for p in lake)
                + 20 * sum(_inside(p, box) for p in river_points)
                + 2 * sum(_inside(p, box) for p in line_points)
                + math.hypot(x - cx, y - cy) / math.hypot(zx1 - zx0, zy1 - zy0)
            )
            if best is None or score < best[0]:
                best = (score, XY(x=round(x, 1), y=round(y, 1)))
    return best[1] if best is not None else XY(x=round(cx, 1), y=round(cy, 1))


def _scan(lo: float, hi: float) -> list[float]:
    if hi < lo:
        return [(lo + hi) / 2]  # the label is wider than the zone: centre it
    count = int((hi - lo) // SCAN_STEP)
    return [lo + i * SCAN_STEP for i in range(count + 1)]


def line_samples(paths: Sequence[str], spacing: float) -> list[Point]:
    return [p for path in paths for p in sample_polyline(path_points(path), spacing)]
