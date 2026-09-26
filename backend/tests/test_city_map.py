"""The dashboard's city map (GET /api/city): geometry derived from the data layer, labels that stay clear."""

import pytest

from gridline.api.city_map import CityMap, build_city_map
from gridline.api.map_geometry import path_points, point_in_polygon, svg_xy
from gridline.api.map_labels import LABEL_UNITS_PER_PX, dot_boxes, glyph_boxes, label_box
from gridline.city.dataset import CityData, load_city_data
from gridline.city.model import City
from tests.conftest import DATA_DIR


@pytest.fixture(scope="module")
def data() -> CityData:
    return load_city_data(DATA_DIR)


@pytest.fixture(scope="module")
def city_map(data: CityData, city: City) -> CityMap:
    return build_city_map(data, city)


def test_svg_coordinates_are_metres_over_ten_with_north_up() -> None:
    assert svg_xy(8200, 4400).model_dump() == {"x": 820, "y": 460}
    assert svg_xy(0, 9000).model_dump() == {"x": 0, "y": 0}


def test_zones_keep_data_layer_ids_geometry_and_population(city_map: CityMap, data: CityData) -> None:
    assert city_map.view_box.model_dump() == {"x": 0, "y": 0, "width": 1200, "height": 900}
    assert [z.id for z in city_map.zones] == [z.id for z in data.zones]
    hillview = next(z for z in city_map.zones if z.id == "Z-HV")
    assert hillview.svg_path == "M820 460 L1140 460 L1140 260 L820 260 Z"
    assert (hillview.name, hillview.population, hillview.drains_to_channel_id) == ("Hillview", 18500, "D-7")


def test_entities_are_the_simulated_ones_placed_from_the_data(city_map: CityMap, city: City) -> None:
    assert [r.id for r in city_map.roads] == [r.id for r in city.roads]
    assert city_map.roads[0].svg_path.startswith("M960 460 L980 410")
    assert set(city_map.roads[0].zone_ids) == {"Z-HV", "Z-RS", "Z-TH"}
    assert [s.id for s in city_map.sensors] == [s.id for s in city.sensors]
    assert [p.id for p in city_map.projects] == [p.id for p in city.projects]
    assert [c.id for c in city_map.crews] == [c.id for c in city.crews]
    assert [b.id for b in city_map.bridges] == [b.id for b in city.bridges]
    kalinadi_bridge = next(b for b in city_map.bridges if b.id == "BR-1")
    assert (kalinadi_bridge.road_id, kalinadi_bridge.crosses_id, kalinadi_bridge.xy.model_dump()) == (
        "RD-03",
        "R-1",
        {"x": 620, "y": 570},
    )
    ht2 = next(p for p in city_map.projects if p.id == "PR-HT2")
    assert (ht2.permit_doc_id, ht2.planned_depth_m, ht2.xy.model_dump()) == (
        "permit-ht-2026-014",
        6.0,
        {"x": 970, "y": 355},
    )
    assert city_map.pump_depot.zone_id == "Z-OT"
    assert [u.id for u in city_map.pump_depot.units] == ["PU-M1", "PU-M2", "PU-M3", "PU-M4"]
    assert {h.id: h.beds_total for h in city_map.hospitals} == {h.id: h.beds_total for h in city.hospitals}


def test_channels_run_through_their_gauge_point_to_their_outfall(city_map: CityMap) -> None:
    d7 = next(c for c in city_map.channels if c.id == "D-7")
    assert "L970 440" in d7.svg_path  # the channel's data-layer location (9700, 4600)
    end_y = float(d7.svg_path.split()[-1])
    assert 570 < end_y < 580  # ends on the Kalinadi centreline
    d8 = next(c for c in city_map.channels if c.id == "D-8")
    assert d8.svg_path.endswith("L970 440")  # outfalls into D-7


def test_map_features_come_from_rivers_and_terrain(city_map: CityMap) -> None:
    kinds = {f.id: f.kind for f in city_map.map_features}
    assert (kinds["R-1"], kinds["R-2"], kinds["R-3"]) == ("river", "river", "lake")
    assert next(f for f in city_map.map_features if f.id == "R-1").label == "Kalinadi"
    contours = [f for f in city_map.map_features if f.kind == "hill_contour"]
    assert contours and all(f.svg_path.startswith("M") for f in contours)


def test_scenarios_and_injection_presets_are_listed(city_map: CityMap) -> None:
    assert [s.name for s in city_map.scenarios] == [
        "normal_city",
        "hillside_landslide",
        "flash_flood",
        "cascading_landslide_flood",
    ]
    assert city_map.injections and all(i.request.event_type for i in city_map.injections)
    assert [t.id for t in city_map.triggers] == [
        "heavy_rain",
        "landslide",
        "drainage_block",
        "flash_flood",
        "industrial_fire",
        "cascading_disaster",
    ]


def test_every_zone_label_sits_inside_its_zone_clear_of_markers_and_the_lake(city_map: CityMap) -> None:
    u = LABEL_UNITS_PER_PX
    graze = 4 * u  # a small dot's box carries a 3 px margin, so a 4 px graze never touches the dot itself
    lake = next(f for f in city_map.map_features if f.id == "R-3")
    lake_points = path_points(lake.svg_path)
    for zone in city_map.zones:
        x0, y0, x1, y1 = label_box(zone.name, zone.label_xy, u)
        xs, ys = zip(*path_points(zone.svg_path), strict=True)
        assert min(xs) <= x0 and x1 <= max(xs) and min(ys) <= y0 and y1 <= max(ys), zone.id
        for mx0, my0, mx1, my1 in glyph_boxes(city_map, u):
            assert x1 <= mx0 or mx1 <= x0 or y1 <= my0 or my1 <= y0, f"{zone.id} label covers an icon"
        for mx0, my0, mx1, my1 in dot_boxes(city_map, u):
            clear = x1 - graze <= mx0 or mx1 <= x0 + graze or y1 - graze <= my0 or my1 <= y0 + graze
            assert clear, f"{zone.id} label covers a sensor or bridge"
        corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1), ((x0 + x1) / 2, (y0 + y1) / 2)]
        assert not any(point_in_polygon(c, lake_points) for c in corners), f"{zone.id} label on the lake"
