"""End-to-end scenario behaviour (spec §11), recalibrated to the Nandipur data layer and its policies."""

from dataclasses import dataclass, field

import pytest

from gridline.city.model import City
from gridline.events.envelope import Event
from gridline.events.types import SEVERITY_ORDER, EventType, Severity
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import ScenarioName
from gridline.simulation.world import WorldSnapshot

ROAD_CLOSURE_CM = 30.0  # policy_thresholds PT-25: roads close at 0.3 m of water


@dataclass
class Run:
    events: list[Event] = field(default_factory=list[Event])
    snapshots: dict[int, WorldSnapshot] = field(default_factory=dict[int, WorldSnapshot])

    def of_type(self, event_type: EventType) -> list[Event]:
        return [e for e in self.events if e.event_type == event_type]

    def tick_of(self, event: Event) -> int:
        return next(t for t, s in self.snapshots.items() if s.sim_time == event.sim_time)


def run(city: City, scenario: ScenarioName, ticks: int, *, halt_at: int | None = None) -> Run:
    engine = SimulationEngine(city)
    result = Run(events=engine.reset(scenario, seed=42))
    result.snapshots[0] = engine.snapshot()
    for tick in range(1, ticks + 1):
        if tick == halt_at:
            depth = engine.snapshot().projects["PR-HT2"].excavation_depth_m
            result.events += engine.inject(
                EventType.INFRASTRUCTURE_CONSTRUCTION,
                {
                    "project_id": "PR-HT2",
                    "status": "halted",
                    "activity": "halted",
                    "excavation_depth_m": depth,
                },
            )
        result.events += engine.advance()
        result.snapshots[tick] = engine.snapshot()
    return result


@pytest.fixture(scope="module")
def cascading(city: City) -> Run:
    return run(city, ScenarioName.CASCADING_LANDSLIDE_FLOOD, 300)


@pytest.fixture(scope="module")
def cascading_halted(city: City) -> Run:
    return run(city, ScenarioName.CASCADING_LANDSLIDE_FLOOD, 300, halt_at=60)


def test_cascading_enters_its_six_stages_in_order(cascading: Run) -> None:
    stages = [(e.payload["tick"], e.payload["stage"]) for e in cascading.of_type(EventType.SCENARIO_STAGE)]
    assert stages == [
        (0, "construction_and_rain"),
        (36, "intensifying_rain"),
        (96, "slope_creep"),
        (144, "critical_slope"),
        (180, "landslide_and_blockage"),
        (204, "downstream_flood"),
    ]


def test_cascading_saturates_and_creeps_the_cut_slope(cascading: Run) -> None:
    sat = {t: s.slopes["SL-HV-1"].saturation for t, s in cascading.snapshots.items()}
    assert sat[95] > sat[36]  # rises during intensifying_rain
    assert sat[180] >= 0.75
    assert any(s.slopes["SL-HV-1"].movement_rate_mm_h > 0 for t, s in cascading.snapshots.items() if t < 144)
    assert cascading.snapshots[216].slopes["SL-HV-1"].cumulative_movement_mm >= 80
    probe = [e for e in cascading.of_type(EventType.ENVIRONMENT_SOIL) if e.payload["probe_id"] == "SM-01"]
    assert max(SEVERITY_ORDER.index(e.severity) for e in probe) == SEVERITY_ORDER.index(Severity.CRITICAL)


def test_cascading_landslide_blocks_d7_and_hillview_access(cascading: Run) -> None:
    failures = cascading.of_type(EventType.INFRASTRUCTURE_FAILURE)
    assert len(failures) == 1
    assert failures[0].payload["asset_id"] == "SL-HV-1"
    assert 180 <= cascading.tick_of(failures[0]) < 204
    after = cascading.snapshots[204]
    assert after.channels["D-7"].blocked_fraction >= 0.7
    assert after.roads["RD-01"].status == "blocked"
    assert after.bridges["BR-4"].status == "closed"
    assert after.projects["PR-HT2"].status == "halted"


def test_cascading_floods_riverside_while_the_kalinadi_rises(cascading: Run, city: City) -> None:
    flood = {t: s for t, s in cascading.snapshots.items() if t >= 204}
    assert max(s.zones["Z-RS"].water_depth_cm for s in flood.values()) >= ROAD_CLOSURE_CM
    assert max(s.rivers["R-1"].level_m for s in flood.values()) > city.river("R-1").warning_stage_m
    assert max(s.channels["D-7"].overflow_m3s for s in flood.values()) > 0
    final = cascading.snapshots[300]
    assert final.roads["RD-02"].status == "blocked"
    assert final.bridges["BR-1"].status == "closed"
    assert final.hospitals["H-2"].er_status == "overwhelmed"


def test_halting_the_excavation_at_t60_prevents_the_landslide(cascading_halted: Run) -> None:
    assert not cascading_halted.of_type(EventType.INFRASTRUCTURE_FAILURE)
    final = cascading_halted.snapshots[300]
    assert final.slopes["SL-HV-1"].cumulative_movement_mm < 80
    assert (
        final.projects["PR-HT2"].excavation_depth_m
        == cascading_halted.snapshots[60].projects["PR-HT2"].excavation_depth_m
    )
    assert final.channels["D-7"].blocked_fraction == 0
    assert final.roads["RD-02"].status == "open"  # Riverside still ponds from the river, but less


def test_hillside_landslide_creeps_without_failing(city: City) -> None:
    hillside = run(city, ScenarioName.HILLSIDE_LANDSLIDE, 288)
    assert not hillside.of_type(EventType.INFRASTRUCTURE_FAILURE)
    assert hillside.snapshots[216].slopes["SL-HV-1"].movement_rate_mm_h > 0
    assert hillside.snapshots[216].stage_index == 3


def test_flash_flood_overloads_d7_and_floods_riverside(city: City) -> None:
    flash = run(city, ScenarioName.FLASH_FLOOD, 240)
    d7 = [e for e in flash.of_type(EventType.ENVIRONMENT_DRAINAGE) if e.payload["channel_id"] == "D-7"]
    stage2 = [e for e in d7 if 96 <= flash.tick_of(e) < 132]
    assert max(e.payload["load_ratio"] for e in stage2) > 1
    stage3 = [s.zones["Z-RS"].water_depth_cm for t, s in flash.snapshots.items() if t >= 132]
    assert max(stage3) > ROAD_CLOSURE_CM
    assert flash.snapshots[240].roads["RD-02"].status == "blocked"
    assert flash.snapshots[240].channels["D-7"].blocked_fraction == 0.25


def test_normal_city_never_exceeds_low(city: City) -> None:
    normal = run(city, ScenarioName.NORMAL_CITY, 288)
    worst = max(normal.events, key=lambda e: SEVERITY_ORDER.index(e.severity))
    assert SEVERITY_ORDER.index(worst.severity) <= SEVERITY_ORDER.index(Severity.LOW), worst
