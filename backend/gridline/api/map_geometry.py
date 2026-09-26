"""Schematic map geometry: data-layer metres to SVG units, path strings, and terrain contours.

The data layer's coordinates are metres, x east 0..12000 and y north 0..9000 (``gridline.city.terrain``).
The map draws them at one SVG unit per ten metres with north up, so SVG y grows southward. Every shape here
is derived from the data layer or the terrain function; nothing is hand-placed.
"""

import math
import re
from collections.abc import Callable, Sequence

from pydantic import BaseModel

from gridline.city.terrain import CITY_BBOX, elevation_m

METRES_PER_UNIT = 10
CONTOUR_LEVELS_M = (240, 300, 400, 500, 600)  # 240 m rings the Civil Lines rise; the rest outline Tekri Hill
CONTOUR_STEP_M = 100  # terrain sampling grid for the contours

Point = tuple[float, float]
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


class XY(BaseModel):
    x: float
    y: float


def svg_point(x_m: float, y_m: float) -> Point:
    """Data-layer metres to SVG units (north up), rounded to 0.1 unit."""
    height_m = CITY_BBOX[3] - CITY_BBOX[1]
    return round((x_m - CITY_BBOX[0]) / METRES_PER_UNIT, 1), round((height_m - y_m) / METRES_PER_UNIT, 1)


def svg_xy(x_m: float, y_m: float) -> XY:
    x, y = svg_point(x_m, y_m)
    return XY(x=x, y=y)


def _num(v: float) -> str:
    return f"{round(v, 1):g}"


def polyline_path(points: Sequence[Point], *, closed: bool = False) -> str:
    """``M x y L x y ...`` (``Z`` when closed) from SVG points."""
    body = " L".join(f"{_num(x)} {_num(y)}" for x, y in points)
    return f"M{body}{' Z' if closed else ''}"


def metres_path(points_m: Sequence[Sequence[float]], *, closed: bool = False) -> str:
    return polyline_path([svg_point(p[0], p[1]) for p in points_m], closed=closed)


def bbox_path(bbox: Sequence[float]) -> str:
    """A zone rectangle from its ``[x0, y0, x1, y1]`` bbox in metres."""
    x0, y0, x1, y1 = bbox
    return metres_path([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)


def path_points(svg_path: str) -> list[Point]:
    """The vertices of an ``M/L`` path (absolute coordinates only), in order."""
    numbers = [float(n) for n in _NUMBER.findall(svg_path)]
    return list(zip(numbers[0::2], numbers[1::2], strict=True))


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Even-odd rule."""
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, [*polygon[1:], polygon[0]], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def sample_polyline(points: Sequence[Point], spacing: float) -> list[Point]:
    """Points every ``spacing`` units along a polyline, vertices included."""
    out: list[Point] = [points[0]] if points else []
    for (x1, y1), (x2, y2) in zip(points, points[1:], strict=False):
        steps = max(1, math.ceil(math.hypot(x2 - x1, y2 - y1) / spacing))
        out += [(x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps) for i in range(1, steps + 1)]
    return out


# ---- terrain contours (marching squares over gridline.city.terrain.elevation_m) ----

_Key = tuple[int, int, int]  # grid node (i, j) plus 0 for a horizontal edge, 1 for a vertical one


def contour_paths(
    level: float, elevation: Callable[[float, float], float] = elevation_m, step: int = CONTOUR_STEP_M
) -> list[str]:
    """SVG paths of the ``level`` metre contour across the city, one per connected line."""
    x0, y0, x1, y1 = CITY_BBOX
    nx, ny = (x1 - x0) // step + 1, (y1 - y0) // step + 1
    grid = [[elevation(x0 + i * step, y0 + j * step) for j in range(ny)] for i in range(nx)]

    def crossing(key: _Key) -> Point:
        i, j, vertical = key
        a = grid[i][j]
        b = grid[i][j + 1] if vertical else grid[i + 1][j]
        t = (level - a) / (b - a)
        return svg_point(x0 + (i + (0 if vertical else t)) * step, y0 + (j + (t if vertical else 0)) * step)

    links: dict[_Key, list[_Key]] = {}
    for i in range(nx - 1):
        for j in range(ny - 1):
            corners = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
            edges: list[_Key] = [(i, j, 0), (i + 1, j, 1), (i, j + 1, 0), (i, j, 1)]  # S, E, N, W
            cut = [e for n, e in enumerate(edges) if (corners[n] >= level) != (corners[(n + 1) % 4] >= level)]
            pairs = (
                [(cut[0], cut[1])] if len(cut) == 2 else [(cut[0], cut[3]), (cut[1], cut[2])] if cut else []
            )
            for a, b in pairs:
                links.setdefault(a, []).append(b)
                links.setdefault(b, []).append(a)
    return [polyline_path([crossing(k) for k in line]) for line in _chains(links)]


def _chains(links: dict[_Key, list[_Key]]) -> list[list[_Key]]:
    """Join edge crossings into lines: open ones from their ends first, then closed loops."""
    seen: set[_Key] = set()
    lines: list[list[_Key]] = []
    starts = [k for k, v in links.items() if len(v) == 1] + list(links)
    for start in starts:
        if start in seen:
            continue
        line, current = [start], start
        seen.add(start)
        while nxt := next((n for n in links[current] if n not in seen), None):
            line.append(nxt)
            seen.add(nxt)
            current = nxt
        if len(line) > 2:
            lines.append(line + ([start] if start in links[current] else []))
    return lines
