"""When scripted scenario events fire (spec §7.1): at their tick, or later once their condition holds.

A conditional event is re-checked every tick until ``tick + deadline_ticks`` and then dropped silently.
"""

from gridline.simulation.scenarios.base import Condition, ScriptedEvent
from gridline.simulation.world import WorldState


def condition_holds(world: WorldState, condition: Condition) -> bool:
    target = condition.target_id
    match condition.metric:
        case "saturation":
            value = world.zones[target].saturation
        case "water_depth_cm":
            value = world.zones[target].water_depth_cm
        case "river_level_m":
            value = world.rivers[target].level_m
        case "slope_cumulative_mm":
            value = world.slopes[target].cumulative_movement_mm
    return value >= condition.min_value


class ScriptSchedule:
    def __init__(self, scripted: tuple[ScriptedEvent, ...]) -> None:
        self._pending = sorted(scripted, key=lambda s: s.tick)

    def due(self, tick: int, world: WorldState) -> list[ScriptedEvent]:
        """Events that fire now, in script order; they and expired events leave the schedule."""
        fire: list[ScriptedEvent] = []
        keep: list[ScriptedEvent] = []
        for scripted in self._pending:
            if scripted.tick > tick:
                keep.append(scripted)
            elif tick > scripted.tick + scripted.deadline_ticks:
                continue
            elif scripted.condition is None or condition_holds(world, scripted.condition):
                fire.append(scripted)
            else:
                keep.append(scripted)
        self._pending = keep
        return fire
