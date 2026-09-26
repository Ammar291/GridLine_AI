"""``GET /api/city``: the static city the dashboard draws, built once from the data layer.

Ids, names and numbers are the data layer's; only entities the simulation models are listed (``City``), placed
from their data-layer coordinates. Live state is not here: it is the ``WorldSnapshot`` in the WebSocket's
``sim.snapshot`` frame and the events that follow it.
"""

from typing import Literal

from pydantic import BaseModel

from gridline.api.injections import INJECTION_PRESETS, InjectionPreset
from gridline.api.map_geometry import (
    CONTOUR_LEVELS_M,
    XY,
    bbox_path,
    contour_paths,
    metres_path,
    path_points,
    polyline_path,
    svg_point,
    svg_xy,
)
from gridline.api.map_labels import (
    LABEL_UNITS_PER_PX,
    dot_boxes,
    glyph_boxes,
    line_samples,
    place_label,
)
from gridline.api.simulation_models import ScenarioInfo, scenario_infos
from gridline.city.dataset import CityData
from gridline.city.model import City, SensorKind
from gridline.city.schema_common import Located
from gridline.city.terrain import CITY_BBOX, river_y


class ViewBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class MapZone(BaseModel):
    id: str
    name: str
    kind: str
    slope_deg: float
    soil_type: str
    population: int
    drains_to_channel_id: str | None
    svg_path: str
    label_xy: XY


class MapRoad(BaseModel):
    id: str
    name: str
    kind: str
    zone_ids: list[str]
    is_evacuation_route: bool
    is_only_access: bool
    svg_path: str


class MapBridge(BaseModel):
    id: str
    name: str
    road_id: str
    zone_id: str
    crosses_id: str
    xy: XY


class MapChannel(BaseModel):
    id: str
    name: str
    zone_id: str
    downstream_zone_id: str
    design_capacity_m3s: float
    current_capacity_m3s: float
    svg_path: str


class MapSlope(BaseModel):
    id: str
    name: str
    zone_id: str
    xy: XY


class MapProject(BaseModel):
    id: str
    name: str
    zone_id: str
    slope_id: str | None
    planned_depth_m: float
    permit_number: str | None
    permit_doc_id: str | None
    xy: XY


class MapSensor(BaseModel):
    id: str
    name: str
    kind: SensorKind
    zone_id: str | None
    target_id: str
    xy: XY


class MapCrew(BaseModel):
    id: str
    name: str
    kind: str
    base_zone_id: str
    xy: XY


class MapShelter(BaseModel):
    id: str
    name: str
    zone_id: str
    capacity: int
    xy: XY


class MapHospital(BaseModel):
    id: str
    name: str
    zone_id: str
    beds_total: int
    xy: XY


class PumpUnit(BaseModel):
    id: str
    name: str
    status: str
    capacity_m3s: float


class PumpDepot(BaseModel):
    zone_id: str
    xy: XY
    units: list[PumpUnit]


class MapFeature(BaseModel):
    id: str
    kind: Literal["river", "lake", "hill_contour"]
    svg_path: str
    label: str | None


class CityMap(BaseModel):
    name: str
    view_box: ViewBox
    zones: list[MapZone]
    roads: list[MapRoad]
    bridges: list[MapBridge]
    channels: list[MapChannel]
    slopes: list[MapSlope]
    projects: list[MapProject]
    sensors: list[MapSensor]
    crews: list[MapCrew]
    shelters: list[MapShelter]
    hospitals: list[MapHospital]
    pump_depot: PumpDepot
    map_features: list[MapFeature]
    scenarios: list[ScenarioInfo]
    injections: list[InjectionPreset]


def build_city_map(data: CityData, city: City) -> CityMap:
    """The dashboard's city: ``city`` says which entities are simulated, ``data`` where they are."""
    width, height = svg_point(CITY_BBOX[2], CITY_BBOX[1])
    draft = CityMap(
        name=city.name,
        view_box=ViewBox(x=0, y=0, width=width, height=height),
        zones=[],
        roads=_roads(data, city),
        bridges=[
            MapBridge(
                id=b.id, name=b.name, road_id=b.road_id, zone_id=b.zone_id, crosses_id=b.crosses_id, xy=xy
            )
            for b in city.bridges
            for xy in [_located(data.bridges, b.id)]
        ],
        channels=_channels(data, city),
        slopes=[
            MapSlope(id=s.id, name=s.name, zone_id=s.zone_id, xy=_located(data.slopes, s.id))
            for s in city.slopes
        ],
        projects=_projects(data, city),
        sensors=[
            MapSensor(
                id=s.id,
                name=next(r.name for r in data.sensors if r.id == s.id),
                kind=s.kind,
                zone_id=s.zone_id,
                target_id=s.target_id,
                xy=_located(data.sensors, s.id),
            )
            for s in city.sensors
        ],
        crews=[
            MapCrew(
                id=c.id, name=c.name, kind=c.kind, base_zone_id=c.base_zone_id, xy=_located(data.crews, c.id)
            )
            for c in city.crews
        ],
        shelters=[
            MapShelter(
                id=s.id, name=s.name, zone_id=s.zone_id, capacity=s.capacity, xy=_located(data.shelters, s.id)
            )
            for s in city.shelters
        ],
        hospitals=[
            MapHospital(
                id=h.id,
                name=h.name,
                zone_id=h.zone_id,
                beds_total=h.beds_total,
                xy=_located(data.hospitals, h.id),
            )
            for h in city.hospitals
        ],
        pump_depot=_pump_depot(data),
        map_features=_features(data),
        scenarios=scenario_infos(),
        injections=list(INJECTION_PRESETS),
    )
    return draft.model_copy(update={"zones": _zones(data, draft)})


def _located[R: Located](records: list[R], record_id: str) -> XY:
    record = next(r for r in records if r.id == record_id)
    return svg_xy(record.x_m, record.y_m)


def _roads(data: CityData, city: City) -> list[MapRoad]:
    records = {r.id: r for r in data.roads}
    roads: list[MapRoad] = []
    for road in city.roads:
        r = records[road.id]
        zone_ids = list(dict.fromkeys([r.zone_id, r.from_zone_id, r.to_zone_id]))
        roads.append(
            MapRoad(
                id=r.id,
                name=r.name,
                kind=r.kind,
                zone_ids=zone_ids,
                is_evacuation_route=r.is_evacuation_route,
                is_only_access=r.is_only_access,
                svg_path=metres_path(r.path),
            )
        )
    return roads


def _channels(data: CityData, city: City) -> list[MapChannel]:
    """Upstream zone centre -> the channel's data-layer point -> its outfall (a channel or the river)."""
    records = {c.id: c for c in data.drainage_channels}
    zones = {z.id: z for z in data.zones}
    channels: list[MapChannel] = []
    for channel in city.channels:
        c = records[channel.id]
        zx0, zy0, zx1, zy1 = zones[c.upstream_zone_id].bbox
        start = svg_point((zx0 + zx1) / 2, (zy0 + zy1) / 2)
        here = svg_point(c.x_m, c.y_m)
        outfall = records.get(c.outfall_channel_id or "")
        end = svg_point(outfall.x_m, outfall.y_m) if outfall else svg_point(c.x_m, river_y(c.x_m))
        points = [start, here, end]
        channels.append(
            MapChannel(
                id=c.id,
                name=c.name,
                zone_id=c.upstream_zone_id,
                downstream_zone_id=c.downstream_zone_id,
                design_capacity_m3s=c.design_capacity_m3s,
                current_capacity_m3s=c.current_capacity_m3s,
                svg_path=polyline_path([p for n, p in enumerate(points) if n == 0 or p != points[n - 1]]),
            )
        )
    return channels


def _projects(data: CityData, city: City) -> list[MapProject]:
    records = {p.id: p for p in data.projects}
    return [
        MapProject(
            id=p.id,
            name=p.name,
            zone_id=p.zone_id,
            slope_id=p.slope_id,
            planned_depth_m=p.planned_depth_m,
            permit_number=p.permit_number,
            permit_doc_id=records[p.id].permit_doc_id,
            xy=svg_xy(records[p.id].x_m, records[p.id].y_m),
        )
        for p in city.projects
    ]


def _pump_depot(data: CityData) -> PumpDepot:
    """The mobile pumps' yard (fixed pumps belong to their channels and are part of its capacity)."""
    mobile = [p for p in data.pump_units if p.kind == "mobile"]
    first = mobile[0]
    return PumpDepot(
        zone_id=first.location_zone_id,
        xy=svg_xy(first.x_m, first.y_m),
        units=[PumpUnit(id=p.id, name=p.name, status=p.status, capacity_m3s=p.capacity_m3s) for p in mobile],
    )


def _features(data: CityData) -> list[MapFeature]:
    water = [
        MapFeature(
            id=r.id,
            kind="lake" if r.kind == "lake" else "river",
            svg_path=metres_path(r.path, closed=r.kind == "lake"),
            label=r.name,
        )
        for r in data.rivers
    ]
    contours = [
        MapFeature(id=f"contour-{level}-{n}", kind="hill_contour", svg_path=path, label=f"{level} m")
        for level in CONTOUR_LEVELS_M
        for n, path in enumerate(contour_paths(level), start=1)
    ]
    return water + contours


def _zones(data: CityData, draft: CityMap) -> list[MapZone]:
    year = data.city.as_of_date.year
    population = {s.zone_id: s.population for s in data.zone_yearly_stats if s.year == year}
    glyphs, dots = glyph_boxes(draft, LABEL_UNITS_PER_PX), dot_boxes(draft, LABEL_UNITS_PER_PX)
    lakes = [path_points(f.svg_path) for f in draft.map_features if f.kind == "lake"]
    rivers = line_samples([f.svg_path for f in draft.map_features if f.kind == "river"], 5)
    lines = line_samples([r.svg_path for r in draft.roads] + [c.svg_path for c in draft.channels], 5)
    zones: list[MapZone] = []
    for z in data.zones:
        (ax, ay), (bx, by) = svg_point(z.bbox[0], z.bbox[1]), svg_point(z.bbox[2], z.bbox[3])
        box = (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
        zones.append(
            MapZone(
                id=z.id,
                name=z.name,
                kind=z.kind,
                slope_deg=z.slope_deg,
                soil_type=z.soil_type,
                population=population[z.id],
                drains_to_channel_id=z.drains_to_channel_id,
                svg_path=bbox_path(z.bbox),
                label_xy=place_label(
                    z.name,
                    box,
                    glyphs=glyphs,
                    dots=dots,
                    lakes=lakes,
                    river_points=rivers,
                    line_points=lines,
                ),
            )
        )
    return zones
