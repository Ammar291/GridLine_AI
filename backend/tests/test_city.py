"""The simulation's City is built from the one Nandipur data layer (backend/data/city/*.yaml)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from gridline.city.dataset import load_city_data
from gridline.city.model import City, DrainageChannel, PolicyThresholds, Zone
from gridline.city.nandipur import build_nandipur, city_from_data
from gridline.errors import UnknownAsset

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_every_data_layer_asset_is_in_the_city(city: City) -> None:
    data = load_city_data(DATA_DIR)
    assert city.name == data.city.name == "Nandipur"
    assert {z.id for z in city.zones} == {z.id for z in data.zones}
    assert {s.id for s in city.slopes} == {s.id for s in data.slopes}
    assert {c.id for c in city.channels} == {c.id for c in data.drainage_channels}
    assert {r.id for r in city.roads} == {r.id for r in data.roads}
    assert {b.id for b in city.bridges} == {b.id for b in data.bridges}
    assert {c.id for c in city.crews} == {c.id for c in data.crews}
    assert {a.id for a in city.ambulances} == {a.id for a in data.ambulances}
    assert {h.id for h in city.hospitals} == {h.id for h in data.hospitals}
    assert {s.id for s in city.shelters} == {s.id for s in data.shelters}
    assert {s.id for s in city.substations} == {s.id for s in data.power_substations}
    # Only gauged rivers, active excavation projects and sensor kinds the simulation observes are modelled.
    assert [r.id for r in city.rivers] == ["R-1"]
    assert {p.id for p in city.projects} == {"PR-HT2", "PR-TQ", "PR-MWM"}
    assert {s.id for s in city.sensors} == {s.id for s in data.sensors if s.kind != "lake_level"}
    assert city.pump_units_available == 4


def test_build_nandipur_equals_city_from_data(city: City) -> None:
    assert build_nandipur(DATA_DIR) == city_from_data(load_city_data(DATA_DIR)) == city


def test_hillview_riverside_chain(city: City) -> None:
    hillview = city.zone("Z-HV")
    assert hillview.kind == "hillside" and hillview.slope_deg == 32
    assert hillview.drains_to_channel_id == "D-7"
    assert hillview.permeability_class == "low"
    assert hillview.impervious_fraction == pytest.approx(0.36)
    assert hillview.area_km2 == pytest.approx(6.4)
    d7 = city.channel("D-7")
    assert (d7.design_capacity_m3s, d7.current_capacity_m3s, d7.blocked_fraction) == (42, 27, 0)
    assert (d7.zone_id, d7.downstream_zone_id, d7.outfall_river_id) == ("Z-HV", "Z-RS", "R-1")
    assert city.channel("D-8").outfall_channel_id == "D-7"
    assert city.channel("D-8").gate_closes_at_river_stage_m == 4.0
    assert city.channel("D-11").pumped_capacity_m3s == pytest.approx(5.0)  # PU-L1 + PU-L3; PU-L2 failed
    slope = city.slope("SL-HV-1")
    assert (slope.zone_id, slope.mean_angle_deg, slope.soil_depth_m, slope.toe_channel_id) == (
        "Z-HV",
        32,
        4.5,
        "D-7",
    )
    project = city.project("PR-HT2")
    assert (project.slope_id, project.permit_number) == ("SL-HV-1", "HT-2026-014")
    assert (project.excavation_depth_m, project.planned_depth_m) == (2.5, 6.0)
    assert city.road("RD-01").is_only_access and city.road("RD-01").is_evacuation_route
    assert city.bridge("BR-4").crosses_id == "D-7" and city.bridge("BR-4").zone_id == "Z-HV"
    assert city.bridge("BR-1").closes_at_river_stage_m == 5.0


def test_river_and_policy_thresholds_come_from_the_data(city: City) -> None:
    r1 = city.river("R-1")
    assert r1.ordinary_stage_m == pytest.approx(1.6)  # surface level 208.6 m over gauge zero 207.0 m
    assert (r1.flood_stage_m, r1.warning_stage_m, r1.danger_stage_m) == (4.2, 5.0, 5.5)
    assert (r1.ordinary_flow_m3s, r1.bankfull_flow_m3s) == (85, 1100)
    t = city.thresholds
    assert (t.rain_1h_watch_mm_h, t.rain_1h_warning_mm_h) == (30, 50)
    assert (t.rain_24h_watch_mm, t.rain_24h_warning_mm, t.rain_24h_critical_mm) == (65, 115, 175)
    assert (t.saturation_warning, t.saturation_critical) == (0.7, 0.85)
    assert (t.channel_ratio_watch, t.channel_ratio_critical) == (0.8, 1.0)
    assert (t.wind_watch_kmh, t.wind_warning_kmh, t.wind_critical_kmh) == (62, 89, 118)
    assert t.road_closure_depth_cm == pytest.approx(30)
    assert set(t.landslide_rain_gauge_ids) == {"RG-01", "RG-02"}  # dmp-2024 s4.2: gauges serving steep slopes


def test_lookups_and_relations(city: City) -> None:
    assert {z.id for z in city.zones_draining_to("D-7")} == {"Z-HV", "Z-TH"}
    assert {c.id for c in city.channels_outfalling_to("D-4")} == {"D-2"}
    assert {r.id for r in city.roads_in("Z-HV")} == {"RD-01"}
    assert [b.id for b in city.bridges_in("Z-HV")] == ["BR-4"]
    assert [p.id for p in city.projects_in("Z-HV")] == ["PR-HT2"]
    assert city.sensor("SM-01").kind == "soil_moisture" and city.sensor("SM-01").target_id == "SL-HV-1"
    assert city.sensor("CL-D7").target_id == "D-7"
    assert city.sensor("RV-02").zone_id is None
    assert city.hospital("H-2").beds_total == 80 and city.hospital("H-2").beds_occupied == 63
    assert city.ambulance("AMB-06").hospital_id == "H-2"
    upstream_first = [c.id for c in city.channels_upstream_first()]
    assert upstream_first.index("D-2") < upstream_first.index("D-4") < upstream_first.index("D-3")
    assert upstream_first.index("D-8") < upstream_first.index("D-7")


def test_unknown_ids_raise(city: City) -> None:
    with pytest.raises(UnknownAsset):
        city.zone("atlantis")
    with pytest.raises(UnknownAsset):
        city.sensor("RG-99")


def test_dangling_reference_rejected() -> None:
    zone = Zone(
        id="Z-A",
        name="A",
        kind="urban",
        slope_deg=1,
        soil_type="clay",
        permeability_class="low",
        impervious_fraction=0.5,
        area_km2=1,
        drains_to_channel_id="missing",
    )
    channel = DrainageChannel(
        id="D-1",
        name="D",
        zone_id="Z-A",
        downstream_zone_id="Z-A",
        design_capacity_m3s=1,
        current_capacity_m3s=1,
    )
    with pytest.raises(ValidationError, match="missing"):
        City(name="Broken", zones=(zone,), channels=(channel,), thresholds=_thresholds())


def _thresholds() -> PolicyThresholds:
    return PolicyThresholds(
        rain_1h_watch_mm_h=30,
        rain_1h_warning_mm_h=50,
        rain_24h_watch_mm=65,
        rain_24h_warning_mm=115,
        rain_24h_critical_mm=175,
        saturation_warning=0.7,
        saturation_critical=0.85,
        channel_ratio_watch=0.8,
        channel_ratio_critical=1.0,
        wind_watch_kmh=62,
        wind_warning_kmh=89,
        wind_critical_kmh=118,
        road_closure_depth_cm=30,
        landslide_rain_gauge_ids=(),
    )
