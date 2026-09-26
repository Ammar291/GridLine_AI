"""The Event envelope (spec §3.1). Payloads are validated against PAYLOAD_MODELS on construction."""

from typing import Any, cast

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from gridline.events.payloads import PAYLOAD_MODELS
from gridline.events.types import EventType, Severity


class Event(BaseModel):
    """One timestamped fact; ``payload`` always conforms to ``PAYLOAD_MODELS[event_type]``, JSON-safe."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    timestamp: AwareDatetime
    sim_time: AwareDatetime
    event_type: EventType
    source: str
    location: str | None = None
    severity: Severity
    payload: dict[str, Any]
    incident_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _validate_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        typed = dict(cast(dict[str, Any], data))
        if "event_type" in typed and "payload" in typed:
            model = PAYLOAD_MODELS[EventType(typed["event_type"])]
            typed["payload"] = model.model_validate(typed["payload"]).model_dump(mode="json")
        return typed


def new_event(
    event_type: EventType,
    payload: BaseModel,
    *,
    event_id: str,
    timestamp: AwareDatetime,
    sim_time: AwareDatetime,
    source: str,
    location: str | None,
    severity: Severity,
    incident_id: str | None = None,
) -> Event:
    """Typed constructor: refuses a payload whose class is not the one registered for ``event_type``."""
    expected = PAYLOAD_MODELS[event_type]
    if type(payload) is not expected:
        raise TypeError(f"{event_type} expects {expected.__name__}, got {type(payload).__name__}")
    return Event(
        event_id=event_id,
        timestamp=timestamp,
        sim_time=sim_time,
        event_type=event_type,
        source=source,
        location=location,
        severity=severity,
        payload=payload.model_dump(mode="json"),
        incident_id=incident_id,
    )
