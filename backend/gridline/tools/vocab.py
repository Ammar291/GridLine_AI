"""Vocabulary of tool inputs and operations tables: Literal values stored in plain String columns."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import StringConstraints

from gridline.city.schema_history import Hazard

__all__ = [
    "RESCUE_CREW_KINDS",
    "AlertLevel",
    "Band",
    "EntityId",
    "EvacuationLevel",
    "Hazard",
    "IncidentBand",
    "IncidentStatus",
    "Priority",
    "Reason",
    "RestrictionKind",
    "Summary",
    "TargetKind",
    "TaskKind",
    "Text500",
    "Title",
    "evacuation_rank",
]

Priority = Literal["low", "medium", "high", "critical"]
Band = Literal["normal", "watch", "warning", "critical"]
IncidentBand = Literal["watch", "warning", "critical"]  # an incident is only opened at watch or above
IncidentStatus = Literal["open", "closed"]
TaskKind = Literal["inspection", "monitoring", "evacuation", "emergency"]
# Assets a task can target; the task's zone is the target's zone (a channel's upstream zone).
TargetKind = Literal["zone", "road", "bridge", "channel", "slope", "project", "shelter", "hospital"]
AlertLevel = Literal["advisory", "warning", "evacuate"]
EvacuationLevel = Literal["voluntary", "mandatory"]
RestrictionKind = Literal["halt", "depth_limit"]

# Crew kinds that rescue people (C-1 rescue, C-4 hill_rescue, C-7 boat); the rest are drainage, road, medical,
# electrical and volunteer crews.
RESCUE_CREW_KINDS: frozenset[str] = frozenset({"rescue", "hill_rescue", "boat"})

_EVACUATION_RANK: Mapping[str, int] = MappingProxyType({"voluntary": 1, "mandatory": 2})


def evacuation_rank(level: str) -> int:
    return _EVACUATION_RANK[level]


EntityId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Text500 = Reason
Summary = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
