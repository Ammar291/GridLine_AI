"""The city dataset: load every ``data/city/*.yaml`` table and check it against itself and the corpus.

``validate_references`` runs before any database write so a bad id fails with the record and field named,
never as a foreign-key error half way through the seed.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml
from pydantic import BaseModel, ConfigDict

from gridline.city.consistency import ReferenceIndex, check_all
from gridline.city.schema_city import (
    CatchmentRecord,
    CityRecord,
    FloodPlainRecord,
    GeologicalZoneRecord,
    HillRecord,
    RiverRecord,
    SlopeRecord,
    SoilProfileRecord,
    ZoneRecord,
)
from gridline.city.schema_common import Record
from gridline.city.schema_history import InfrastructureChangeRecord, PolicyThresholdRecord
from gridline.city.schema_infra import (
    BridgeRecord,
    CriticalInfrastructureRecord,
    DamRecord,
    DrainageChannelRecord,
    PowerSubstationRecord,
    ProjectRecord,
    PumpUnitRecord,
    RoadRecord,
    SensorRecord,
    TunnelRecord,
    WaterFacilityRecord,
)
from gridline.city.schema_people import (
    AmbulanceRecord,
    CrewRecord,
    FireStationRecord,
    FireTruckRecord,
    HospitalBedRecord,
    HospitalRecord,
    PoliceStationRecord,
    ResidentialAreaRecord,
    SchoolRecord,
    ShelterRecord,
    ZoneYearlyStatsRecord,
)

if TYPE_CHECKING:
    from gridline.db.seed.corpus import ParsedDocument


class CityData(BaseModel):
    """Every YAML table, one field per table named exactly like it."""

    model_config = ConfigDict(extra="forbid")

    city: CityRecord
    zones: list[ZoneRecord]
    geological_zones: list[GeologicalZoneRecord]
    soil_profiles: list[SoilProfileRecord]
    catchments: list[CatchmentRecord]
    rivers: list[RiverRecord]
    hills: list[HillRecord]
    slopes: list[SlopeRecord]
    flood_plains: list[FloodPlainRecord]
    drainage_channels: list[DrainageChannelRecord]
    pump_units: list[PumpUnitRecord]
    roads: list[RoadRecord]
    bridges: list[BridgeRecord]
    tunnels: list[TunnelRecord]
    dams: list[DamRecord]
    power_substations: list[PowerSubstationRecord]
    water_facilities: list[WaterFacilityRecord]
    projects: list[ProjectRecord]
    critical_infrastructure: list[CriticalInfrastructureRecord]
    sensors: list[SensorRecord]
    hospitals: list[HospitalRecord]
    hospital_beds: list[HospitalBedRecord]
    ambulances: list[AmbulanceRecord]
    fire_stations: list[FireStationRecord]
    fire_trucks: list[FireTruckRecord]
    police_stations: list[PoliceStationRecord]
    crews: list[CrewRecord]
    shelters: list[ShelterRecord]
    zone_yearly_stats: list[ZoneYearlyStatsRecord]
    residential_areas: list[ResidentialAreaRecord]
    schools: list[SchoolRecord]
    infrastructure_changes: list[InfrastructureChangeRecord]
    policy_thresholds: list[PolicyThresholdRecord]

    def tables(self) -> Iterator[tuple[str, list[Record]]]:
        """(table name, records) for every list table, in declaration order."""
        for name in type(self).model_fields:
            if name != "city":
                yield name, cast(list[Record], getattr(self, name))


def load_city_data(data_dir: Path) -> CityData:
    """Read and validate ``data_dir/city/*.yaml`` (each file maps table name -> list of records)."""
    tables: dict[str, Any] = {}
    for path in sorted((data_dir / "city").glob("*.yaml")):
        loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"{path.name}: expected a mapping of table name -> records")
        for table, rows in cast(dict[str, Any], loaded).items():
            if table in tables:
                raise ValueError(f"{path.name}: table {table!r} is defined in more than one file")
            tables[table] = rows
    city_rows = tables.get("city")
    if not isinstance(city_rows, list) or len(cast(list[Any], city_rows)) != 1:
        raise ValueError("city.yaml: 'city' must be a list with exactly one record")
    tables["city"] = cast(list[Any], city_rows)[0]
    return CityData.model_validate(tables)


def validate_references(data: CityData, docs: "list[ParsedDocument]") -> list[str]:
    """Human-readable problems in the dataset and corpus; an empty list means consistent."""
    return check_all(data, docs)


__all__ = ["CityData", "ReferenceIndex", "load_city_data", "validate_references"]
