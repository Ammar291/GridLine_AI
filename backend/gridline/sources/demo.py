"""DEMO mode: the synthetic Nandipur simulation, driven by the operator through ``/api/simulation``."""

from gridline.events.envelope import Event
from gridline.events.payloads import DataMode, SourceStatus
from gridline.simulation.runner import SimulationRunner

DEMO_STATUS = SourceStatus(
    mode="demo", label="DEMO — Nandipur", city="Nandipur", provider="Synthetic simulation"
)


class DemoDataSource:
    """Leaving DEMO pauses a running simulation; coming back resumes it only if the switch paused it."""

    def __init__(self, runner: SimulationRunner) -> None:
        self.runner = runner
        self._paused_by_switch = False

    @property
    def mode(self) -> DataMode:
        return "demo"

    async def start(self) -> None:
        if self._paused_by_switch and self.runner.state == "paused":
            await self.runner.resume()
        self._paused_by_switch = False

    async def stop(self) -> None:
        if self.runner.state == "running":
            await self.runner.pause()
            self._paused_by_switch = True

    def status(self) -> SourceStatus:
        return DEMO_STATUS

    def latest(self) -> list[Event]:
        return []  # the WebSocket snapshot already carries the whole simulated world
