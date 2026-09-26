"""Terrain of Nandipur: the single source of truth for every elevation in the data layer (spec §4).

Coordinates are schematic metres, x 0..12000 east and y 0..9000 north.
"""

import math

CITY_BBOX: tuple[int, int, int, int] = (0, 0, 12000, 9000)


def river_y(x: float) -> float:
    """Northing of the Kalinadi (R-1) centreline at easting ``x``."""
    return 3000 + 250 * math.sin((x - 6000) / 3000)


def elevation_m(x: float, y: float) -> float:
    """Ground elevation in metres, rounded to 0.1 m."""
    d = y - river_y(x)
    base = 212 + (0.003 * d if d >= 0 else 0.0015 * -d)  # north bank rises 3 m/km, south bank 1.5 m/km
    hill = 400 * math.exp(-(((x - 11000) / 2400) ** 2 + ((y - 8600) / 2000) ** 2))  # Tekri Hill
    plateau = 30 * math.exp(-(((x - 5500) / 1500) ** 2 + ((y - 6500) / 900) ** 2))  # Civil Lines rise
    lake = -4 * math.exp(-(((x - 1800) / 1100) ** 2 + ((y - 1500) / 800) ** 2))  # Nandi Lake basin
    return round(base + hill + plateau + lake, 1)


def elevation_grid(step: int = 500) -> list[tuple[int, int, float]]:
    """(x, y, elevation) over the city bbox, bounds inclusive, x-major order."""
    x0, y0, x1, y1 = CITY_BBOX
    return [(x, y, elevation_m(x, y)) for x in range(x0, x1 + 1, step) for y in range(y0, y1 + 1, step)]
