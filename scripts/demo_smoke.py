"""Headless smoke run of the primary scenario (spec §11). Must pass before any demo.

Replays ``cascading_landslide_flood`` with seed 42 for 300 ticks, prints a per-stage summary and asserts the
cascade: the six stages in order, the SL-HV-1 landslide, D-7 blocked, Riverside flooded past the road-closure
depth and the Kalinadi above its warning stage. It then replays the same storm with PR-HT2 halted at t=60 and
asserts that the landslide does not happen. Exit code 1 on any failed check. No database, no network.

Run from the repository root:  uv run python scripts/demo_smoke.py
or from backend/:               uv run python ../scripts/demo_smoke.py
"""
# ruff: noqa: E402  (the gridline imports must follow the bootstrap that re-runs the script inside backend/)

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"

try:
    import gridline  # noqa: F401  # pyright: ignore[reportUnusedImport]
except ModuleNotFoundError:  # started outside the backend project (e.g. from the repo root): re-run inside it
    command = ["uv", "run", "--project", str(BACKEND), "python", str(Path(__file__).resolve()), *sys.argv[1:]]
    sys.exit(subprocess.run(command, check=False).returncode)

from gridline.city.nandipur import build_nandipur
from gridline.events.envelope import Event
from gridline.events.types import EventType
from gridline.simulation.engine import SimulationEngine
from gridline.simulation.scenarios import ScenarioName
from gridline.simulation.world import WorldSnapshot

SCENARIO = ScenarioName.CASCADING_LANDSLIDE_FLOOD
SEED = 42
TICKS = 300
HALT_AT = 60
EXPECTED_STAGES = [
    "construction_and_rain",
    "intensifying_rain",
    "slope_creep",
    "critical_slope",
    "landslide_and_blockage",
    "downstream_flood",
]


def replay(
    engine: SimulationEngine, halt_at: int | None = None
) -> tuple[list[Event], dict[int, WorldSnapshot]]:
    events = engine.reset(SCENARIO, SEED)
    snapshots = {0: engine.snapshot()}
    for tick in range(1, TICKS + 1):
        if tick == halt_at:
            depth = engine.snapshot().projects["PR-HT2"].excavation_depth_m
            events += engine.inject(
                EventType.INFRASTRUCTURE_CONSTRUCTION,
                {
                    "project_id": "PR-HT2",
                    "status": "halted",
                    "activity": "halted",
                    "excavation_depth_m": depth,
                },
            )
        events += engine.advance()
        snapshots[tick] = engine.snapshot()
    return events, snapshots


def summarise(engine: SimulationEngine, events: list[Event], snapshots: dict[int, WorldSnapshot]) -> None:
    stages = engine.scenario.stages
    print(
        f"{'stage':<24}{'ticks':>9}{'rain24h':>9}{'SM-01 sat':>10}{'creep':>8}{'moved':>8}"
        f"{'D-7 load':>9}{'RS water':>9}{'R-1':>6}  events"
    )
    for index, stage in enumerate(stages):
        end = stages[index + 1].start_tick - 1 if index + 1 < len(stages) else TICKS
        window = [snapshots[t] for t in range(stage.start_tick, end + 1)]
        notable = [
            f"{e.event_type.split('.')[-1]}:{_asset(e)}"
            for e in events
            if _notable(e) and window[0].sim_time <= e.sim_time <= window[-1].sim_time
        ]
        d7 = max(s.channels["D-7"].flow_m3s / max(s.channels["D-7"].capacity_m3s, 1e-9) for s in window)
        print(
            f"{stage.name:<24}{stage.start_tick:>4}-{end:<4}"
            f"{max(s.zones['Z-HV'].rain_24h_mm for s in window):>9.0f}"
            f"{max(s.slopes['SL-HV-1'].saturation for s in window):>10.2f}"
            f"{max(s.slopes['SL-HV-1'].movement_rate_mm_h for s in window):>8.1f}"
            f"{window[-1].slopes['SL-HV-1'].cumulative_movement_mm:>8.0f}"
            f"{d7:>9.2f}{max(s.zones['Z-RS'].water_depth_cm for s in window):>9.1f}"
            f"{max(s.rivers['R-1'].level_m for s in window):>6.2f}  {', '.join(notable)}"
        )


def _notable(event: Event) -> bool:
    """State changes worth a line; routine excavation progress reports are left out."""
    if event.event_type == EventType.INFRASTRUCTURE_CONSTRUCTION:
        return event.payload["status"] == "halted"
    return event.event_type.startswith(("infrastructure.", "emergency."))


def _asset(event: Event) -> str:
    keys = (
        "asset_id",
        "channel_id",
        "road_id",
        "bridge_id",
        "project_id",
        "crew_id",
        "ambulance_id",
        "hospital_id",
        "shelter_id",
    )
    return next(str(event.payload[k]) for k in keys if k in event.payload)


def main() -> int:
    city = build_nandipur()
    engine = SimulationEngine(city)
    river = city.river("R-1")
    failures: list[str] = []

    def check(ok: bool, message: str) -> None:
        print(f"  [{'ok' if ok else 'FAIL'}] {message}")
        if not ok:
            failures.append(message)

    print(f"GridLine AI demo smoke: {SCENARIO} seed {SEED}, {TICKS} ticks of {engine.minutes_per_tick} min\n")
    events, snapshots = replay(engine)
    summarise(engine, events, snapshots)
    final = snapshots[TICKS]
    stages = [e.payload["stage"] for e in events if e.event_type == EventType.SCENARIO_STAGE]
    landslides = [e for e in events if e.event_type == EventType.INFRASTRUCTURE_FAILURE]
    flood = [s for t, s in snapshots.items() if t >= 204]
    print("\nchecks")
    check(stages == EXPECTED_STAGES, f"stages in order: {' -> '.join(stages)}")
    check(
        len(landslides) == 1 and landslides[0].payload["asset_id"] == "SL-HV-1", "SL-HV-1 landslide occurred"
    )
    check(
        final.channels["D-7"].blocked_fraction >= 0.7,
        f"D-7 blocked {final.channels['D-7'].blocked_fraction:.2f}",
    )
    depth = max(s.zones["Z-RS"].water_depth_cm for s in flood)
    check(depth >= city.thresholds.road_closure_depth_cm, f"Riverside flooded to {depth:.1f} cm")
    level = max(s.rivers["R-1"].level_m for s in flood)
    check(
        level > river.warning_stage_m, f"Kalinadi peaked at {level:.2f} m (warning {river.warning_stage_m} m)"
    )
    check(
        final.roads["RD-01"].status == "blocked" and final.roads["RD-02"].status == "blocked",
        "Hill Road and Riverside Bypass blocked",
    )

    halted_events, halted = replay(engine, halt_at=HALT_AT)
    moved = halted[TICKS].slopes["SL-HV-1"].cumulative_movement_mm
    no_failure = not [e for e in halted_events if e.event_type == EventType.INFRASTRUCTURE_FAILURE]
    check(
        no_failure and moved < 80,
        f"halting PR-HT2 at t={HALT_AT} prevents the landslide ({moved:.0f} mm moved)",
    )

    print(f"\n{'PASS' if not failures else 'FAIL'}: {len(events)} events, {len(failures)} failed checks")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
