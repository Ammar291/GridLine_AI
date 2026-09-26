"""Tool registry (spec §10). ``build_registry()`` returns a fresh registry of all 21 tools.

The app will hang it on ``app.state``; ``describe()`` is what the ``recommend`` node will hand to the model.
"""

from typing import Any, Literal

from pydantic import BaseModel

from gridline.tools.base import ActionTool, ReadTool
from gridline.tools.construction import CreateConstructionRestriction
from gridline.tools.evacuation import CreateEvacuationOrder, CreateEvacuationTask
from gridline.tools.hospitals import GetHospitalCapacity, ReserveHospitalBeds
from gridline.tools.incidents import CreateEmergencyTask, CreateIncident, UpdateIncident
from gridline.tools.prevention import CreateInspectionOrder, CreateMonitoringTask, IssuePreventiveAlert
from gridline.tools.resources import (
    DispatchAmbulance,
    DispatchRescueTeam,
    GetAvailableAmbulances,
    GetAvailableRescueTeams,
)
from gridline.tools.roads import CloseRoad, GetRoadStatus, ReopenRoad
from gridline.tools.shelters import CloseShelter, GetShelterCapacity, OpenShelter

AnyActionTool = ActionTool[Any, Any]
AnyReadTool = ReadTool[Any, Any]


class ToolSpec(BaseModel):
    name: str
    description: str
    kind: Literal["read", "action"]
    approval: Literal["auto", "required", "conditional"]
    input_schema: dict[str, Any]


def _approval(tool: AnyActionTool) -> Literal["auto", "required", "conditional"]:
    if any("requires_approval" in vars(cls) for cls in type(tool).__mro__ if cls is not ActionTool):
        return "conditional"  # approval depends on the input (issue_preventive_alert)
    return "required" if tool.approval_required else "auto"


class ToolRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, AnyActionTool] = {}
        self._reads: dict[str, AnyReadTool] = {}

    def register(self, tool: AnyActionTool | AnyReadTool) -> None:
        if tool.name in self._actions or tool.name in self._reads:
            raise ValueError(f"tool '{tool.name}' is already registered")
        if isinstance(tool, ActionTool):
            self._actions[tool.name] = tool
        else:
            self._reads[tool.name] = tool

    def action(self, name: str) -> AnyActionTool:
        return self._actions[name]

    def read(self, name: str) -> AnyReadTool:
        return self._reads[name]

    def names(self) -> list[str]:
        return [*self._reads, *self._actions]

    def describe(self) -> list[ToolSpec]:
        reads = [
            ToolSpec(
                name=t.name,
                description=t.description,
                kind="read",
                approval="auto",
                input_schema=t.Input.model_json_schema(),
            )
            for t in self._reads.values()
        ]
        actions = [
            ToolSpec(
                name=t.name,
                description=t.description,
                kind="action",
                approval=_approval(t),
                input_schema=t.Input.model_json_schema(),
            )
            for t in self._actions.values()
        ]
        return reads + actions


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    tools: list[AnyActionTool | AnyReadTool] = [
        GetAvailableRescueTeams(),
        DispatchRescueTeam(),
        GetAvailableAmbulances(),
        DispatchAmbulance(),
        GetShelterCapacity(),
        OpenShelter(),
        CloseShelter(),
        GetHospitalCapacity(),
        ReserveHospitalBeds(),
        GetRoadStatus(),
        CloseRoad(),
        ReopenRoad(),
        CreateInspectionOrder(),
        CreateMonitoringTask(),
        CreateConstructionRestriction(),
        IssuePreventiveAlert(),
        CreateEvacuationOrder(),
        CreateEvacuationTask(),
        CreateIncident(),
        UpdateIncident(),
        CreateEmergencyTask(),
    ]
    for tool in tools:
        registry.register(tool)
    return registry
