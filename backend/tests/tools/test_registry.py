import pytest

from gridline.tools.registry import ToolRegistry, build_registry
from gridline.tools.roads import GetRoadStatus

READS = {
    "get_available_rescue_teams",
    "get_available_ambulances",
    "get_shelter_capacity",
    "get_hospital_capacity",
    "get_road_status",
}
REQUIRED = {
    "dispatch_rescue_team",
    "dispatch_ambulance",
    "open_shelter",
    "close_shelter",
    "reserve_hospital_beds",
    "close_road",
    "reopen_road",
    "create_construction_restriction",
    "create_evacuation_order",
}
CONDITIONAL = {"issue_preventive_alert"}
AUTO_ACTIONS = {
    "create_inspection_order",
    "create_monitoring_task",
    "create_evacuation_task",
    "create_incident",
    "update_incident",
    "create_emergency_task",
}


def test_registry_has_the_21_tools_of_the_brief():
    registry = build_registry()
    assert set(registry.names()) == READS | REQUIRED | CONDITIONAL | AUTO_ACTIONS
    assert len(registry.names()) == 21


def test_describe_reports_kind_and_approval_mode():
    specs = {s.name: s for s in build_registry().describe()}
    assert {n for n, s in specs.items() if s.kind == "read"} == READS
    assert {n for n, s in specs.items() if s.approval == "required"} == REQUIRED
    assert {n for n, s in specs.items() if s.approval == "conditional"} == CONDITIONAL
    assert {n for n, s in specs.items() if s.kind == "action" and s.approval == "auto"} == AUTO_ACTIONS
    assert all(s.approval == "auto" for s in specs.values() if s.kind == "read")


def test_every_input_schema_forbids_unknown_keys():
    for spec in build_registry().describe():
        assert spec.input_schema["additionalProperties"] is False, spec.name
        assert spec.description, spec.name
        has_key = "idempotency_key" in spec.input_schema["properties"]
        assert has_key == (spec.kind == "action"), spec.name


def test_lookup_by_kind_and_errors():
    registry = build_registry()
    assert registry.action("close_road").name == "close_road"
    assert registry.read("get_road_status").name == "get_road_status"
    with pytest.raises(KeyError):
        registry.action("get_road_status")
    with pytest.raises(KeyError):
        registry.read("launch_rocket")
    with pytest.raises(ValueError, match="already registered"):
        registry.register(GetRoadStatus())


def test_each_call_builds_an_independent_registry():
    empty = ToolRegistry()
    assert empty.names() == []
    first, second = build_registry(), build_registry()
    assert first is not second and first.action("close_road") is not second.action("close_road")
