from gridline.city.terrain import CITY_BBOX, elevation_grid, elevation_m, river_y


def test_river_centreline_passes_through_6000_3000() -> None:
    assert river_y(6000) == 3000


def test_river_bank_datum_is_212_on_the_centreline() -> None:
    assert elevation_m(6000, 3000) == 212.0


def test_tekri_summit_is_high_and_lake_basin_is_low() -> None:
    assert elevation_m(11000, 8600) > 600
    assert elevation_m(1800, 1500) < 212


def test_grid_covers_city_bbox() -> None:
    grid = elevation_grid()
    assert len(grid) == 25 * 19
    xs = {x for x, _, _ in grid}
    ys = {y for _, y, _ in grid}
    assert min(xs) == CITY_BBOX[0] and max(xs) == CITY_BBOX[2]
    assert min(ys) == CITY_BBOX[1] and max(ys) == CITY_BBOX[3]
    assert all(z == elevation_m(x, y) for x, y, z in grid)
